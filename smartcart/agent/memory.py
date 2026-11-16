"""Persistent conversation memory: a LangGraph checkpointer stored in PostgreSQL.

Before, chat memory lived in RAM (InMemorySaver) and was lost when the server
restarted (the cart survived, the conversation did not). PostgresSaver keeps every
graph checkpoint in two tables, so a conversation continues after a restart.

Why not the official langgraph-checkpoint-postgres package? It needs psycopg 3,
whose native library is blocked on the project machine; this saver uses the same
SQLAlchemy/psycopg2 connection as the rest of the project. It implements the
standard BaseCheckpointSaver contract (get_tuple / list / put / put_writes /
delete_thread), serialising with LangGraph's own serializer.

    agent_checkpoints        one row per graph step: the full state (channel values)
    agent_checkpoint_writes  pending writes of tasks inside a step (for resume)
"""
import random
from collections.abc import Iterator, Sequence
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (WRITES_IDX_MAP, BaseCheckpointSaver, ChannelVersions, Checkpoint,
                                       CheckpointMetadata, CheckpointTuple, get_checkpoint_id,
                                       get_checkpoint_metadata, writes_sort_key)
from sqlalchemy import text

from smartcart.db import get_engine

DDL = """
CREATE TABLE IF NOT EXISTS agent_checkpoints (
    thread_id      TEXT  NOT NULL,
    checkpoint_ns  TEXT  NOT NULL DEFAULT '',
    checkpoint_id  TEXT  NOT NULL,
    parent_id      TEXT,
    type           TEXT  NOT NULL,
    checkpoint     BYTEA NOT NULL,
    metadata_type  TEXT  NOT NULL,
    metadata       BYTEA NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE IF NOT EXISTS agent_checkpoint_writes (
    thread_id      TEXT    NOT NULL,
    checkpoint_ns  TEXT    NOT NULL DEFAULT '',
    checkpoint_id  TEXT    NOT NULL,
    task_id        TEXT    NOT NULL,
    idx            INTEGER NOT NULL,
    channel        TEXT    NOT NULL,
    type           TEXT    NOT NULL,
    value          BYTEA   NOT NULL,
    task_path      TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
"""


def ensure_memory_tables(engine=None):
    with (engine or get_engine()).begin() as conn:
        for stmt in DDL.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))


def delete_thread_memory(conn, thread_id: str):
    """Remove one conversation's memory (used when test/evaluation sessions are cleaned up)."""
    conn.execute(text("DELETE FROM agent_checkpoint_writes WHERE thread_id = :t"), {"t": thread_id})
    conn.execute(text("DELETE FROM agent_checkpoints WHERE thread_id = :t"), {"t": thread_id})


class PostgresSaver(BaseCheckpointSaver[str]):
    def __init__(self, engine=None, *, serde=None):
        super().__init__(serde=serde)
        self.engine = engine or get_engine()
        ensure_memory_tables(self.engine)

    # ---------------------------------------------------------------- read
    def _tuple(self, conn, row) -> CheckpointTuple:
        thread_id, ns, cid = row["thread_id"], row["checkpoint_ns"], row["checkpoint_id"]
        writes = conn.execute(text("""
            SELECT task_id, idx, channel, type, value, task_path FROM agent_checkpoint_writes
            WHERE thread_id = :t AND checkpoint_ns = :ns AND checkpoint_id = :c"""),
            {"t": thread_id, "ns": ns, "c": cid}).mappings().all()
        writes = sorted(writes, key=lambda w: writes_sort_key(w["task_path"], w["task_id"], w["idx"]))
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": cid}},
            checkpoint=self.serde.loads_typed((row["type"], bytes(row["checkpoint"]))),
            metadata=self.serde.loads_typed((row["metadata_type"], bytes(row["metadata"]))),
            parent_config=({"configurable": {"thread_id": thread_id, "checkpoint_ns": ns,
                                             "checkpoint_id": row["parent_id"]}}
                           if row["parent_id"] else None),
            pending_writes=[(w["task_id"], w["channel"], self.serde.loads_typed((w["type"], bytes(w["value"]))))
                            for w in writes],
        )

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        cid = get_checkpoint_id(config)
        sql = "SELECT * FROM agent_checkpoints WHERE thread_id = :t AND checkpoint_ns = :ns"
        sql += " AND checkpoint_id = :c" if cid else " ORDER BY checkpoint_id DESC LIMIT 1"
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"t": thread_id, "ns": ns, "c": cid}).mappings().first()
            return self._tuple(conn, row) if row else None

    def list(self, config: Optional[RunnableConfig], *, filter: Optional[dict[str, Any]] = None,
             before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        where, params = [], {}
        if config:
            where.append("thread_id = :t")
            params["t"] = config["configurable"]["thread_id"]
            if (ns := config["configurable"].get("checkpoint_ns")) is not None:
                where.append("checkpoint_ns = :ns")
                params["ns"] = ns
            if cid := get_checkpoint_id(config):
                where.append("checkpoint_id = :c")
                params["c"] = cid
        if before and (bid := get_checkpoint_id(before)):
            where.append("checkpoint_id < :b")
            params["b"] = bid
        sql = "SELECT * FROM agent_checkpoints" + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY thread_id, checkpoint_ns, checkpoint_id DESC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
            out = []
            for row in rows:
                if limit is not None and len(out) >= limit:
                    break
                tup = self._tuple(conn, row)
                if filter and not all(tup.metadata.get(k) == v for k, v in filter.items()):
                    continue
                out.append(tup)
        yield from out

    # ---------------------------------------------------------------- write
    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata,
            new_versions: ChannelVersions) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        ctype, cblob = self.serde.dumps_typed(checkpoint)
        mtype, mblob = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO agent_checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_id, type,
                                               checkpoint, metadata_type, metadata)
                VALUES (:t, :ns, :c, :p, :ty, :cb, :mt, :mb)
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) DO UPDATE
                SET type = EXCLUDED.type, checkpoint = EXCLUDED.checkpoint,
                    metadata_type = EXCLUDED.metadata_type, metadata = EXCLUDED.metadata"""),
                {"t": thread_id, "ns": ns, "c": checkpoint["id"], "p": config["configurable"].get("checkpoint_id"),
                 "ty": ctype, "cb": cblob, "mt": mtype, "mb": mblob})
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns, "checkpoint_id": checkpoint["id"]}}

    def put_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str,
                   task_path: str = "") -> None:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        cid = config["configurable"]["checkpoint_id"]
        with self.engine.begin() as conn:
            for i, (channel, value) in enumerate(writes):
                idx = WRITES_IDX_MAP.get(channel, i)
                vtype, vblob = self.serde.dumps_typed(value)
                # regular writes are kept once; special writes (errors, interrupts) are overwritten
                conflict = "DO NOTHING" if idx >= 0 else \
                    "DO UPDATE SET channel = EXCLUDED.channel, type = EXCLUDED.type, value = EXCLUDED.value"
                conn.execute(text(f"""
                    INSERT INTO agent_checkpoint_writes
                        (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value, task_path)
                    VALUES (:t, :ns, :c, :task, :idx, :ch, :ty, :v, :tp)
                    ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) {conflict}"""),
                    {"t": thread_id, "ns": ns, "c": cid, "task": task_id, "idx": idx, "ch": channel,
                     "ty": vtype, "v": vblob, "tp": task_path})

    def delete_thread(self, thread_id: str) -> None:
        with self.engine.begin() as conn:
            delete_thread_memory(conn, thread_id)

    def get_next_version(self, current: Optional[str], channel: None = None) -> str:
        # same scheme as InMemorySaver: zero-padded counter + random suffix, sortable as text
        current_v = 0 if current is None else int(current) if isinstance(current, int) \
            else int(str(current).split(".")[0])
        return f"{current_v + 1:032}.{random.random():016}"
