"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  addMemoryEntity,
  deleteMemory,
  fetchMemories,
  fetchMemoryEntities,
  removeMemoryEntity,
  renameMemoryEntity,
} from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { Memory, MemoryEntity } from "@/types";

export default function Memories() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [entityKey, setEntityKey] = useState<string>("");
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/login");
  }, [authLoading, isAuthenticated, router]);

  const {
    data: memories = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["memories", entityKey],
    queryFn: () => fetchMemories(entityKey || undefined),
    enabled: isAuthenticated,
  });

  const { data: entities = [] } = useQuery({
    queryKey: ["memoryEntities"],
    queryFn: fetchMemoryEntities,
    enabled: isAuthenticated,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["memories"] });
    queryClient.invalidateQueries({ queryKey: ["memoryEntities"] });
  };

  const remove = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: invalidate,
  });

  const groups = useMemo(() => groupByEntity(memories, entityKey), [memories, entityKey]);

  if (authLoading || !isAuthenticated) {
    return (
      <div className="app-shell">
        <div className="fill-center">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppBar active="memories" />
      <div className="container" style={{ flex: 1 }}>
        <div className="app-bar" style={{ borderBottom: "none", height: "auto", paddingTop: 22 }}>
          <h1 style={{ fontSize: 24, margin: 0 }}>Your memories</h1>
        </div>

        {entities.length > 0 && (
          <div className="entity-chips">
            <button
              type="button"
              className={`entity-chip${entityKey === "" ? " active" : ""}`}
              onClick={() => setEntityKey("")}
            >
              All
            </button>
            {entities.map((e) => (
              <EntityChip
                key={e.id}
                entity={e}
                active={entityKey === e.key}
                onSelect={() => setEntityKey(e.key)}
                onRenamed={(key) => {
                  invalidate();
                  if (entityKey === e.key) setEntityKey(key);
                }}
              />
            ))}
          </div>
        )}

        {isLoading ? (
          <div className="fill-center">
            <div className="spinner" />
          </div>
        ) : isError ? (
          <p className="empty">
            Couldn&apos;t load memories
            {error instanceof Error ? `: ${error.message}` : ""}.{" "}
            <button type="button" onClick={() => void refetch()}>
              Retry
            </button>
          </p>
        ) : memories.length === 0 ? (
          <p className="empty">
            Nothing saved yet. Head to the chat and tell me something to remember.
          </p>
        ) : (
          <div className="mem-list">
            {groups.map((g) => (
              <section key={g.key} className="entity-group">
                {g.title && <h2 className="entity-heading">{g.title}</h2>}
                {g.memories.map((m) => (
                  <MemoryRow
                    key={m.id}
                    memory={m}
                    editing={editingId === m.id}
                    onToggleEdit={() =>
                      setEditingId((cur) => (cur === m.id ? null : m.id))
                    }
                    onDelete={() => remove.mutate(m.id)}
                    deleting={remove.isPending && remove.variables === m.id}
                    onEntityClick={(key) => setEntityKey(key)}
                    onRelationsChanged={invalidate}
                    knownEntities={entities}
                  />
                ))}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function groupByEntity(
  memories: Memory[],
  filterKey: string,
): { key: string; title: string; memories: Memory[] }[] {
  if (filterKey) {
    const name =
      memories
        .flatMap((m) => m.entities || [])
        .find((e) => e.key === filterKey)?.name || filterKey;
    return [{ key: filterKey, title: name, memories }];
  }

  const byKey = new Map<string, { title: string; memories: Memory[]; seen: Set<string> }>();
  const ungrouped: Memory[] = [];

  for (const m of memories) {
    const ents = m.entities || [];
    if (ents.length === 0) {
      ungrouped.push(m);
      continue;
    }
    const primary = ents[0];
    let bucket = byKey.get(primary.key);
    if (!bucket) {
      bucket = { title: primary.name, memories: [], seen: new Set() };
      byKey.set(primary.key, bucket);
    }
    if (!bucket.seen.has(m.id)) {
      bucket.seen.add(m.id);
      bucket.memories.push(m);
    }
  }

  const groups = [...byKey.entries()]
    .sort((a, b) => a[1].title.localeCompare(b[1].title))
    .map(([key, g]) => ({ key, title: g.title, memories: g.memories }));

  if (ungrouped.length) {
    groups.push({ key: "_other", title: "Other", memories: ungrouped });
  }
  return groups;
}

function EntityChip({
  entity,
  active,
  onSelect,
  onRenamed,
}: {
  entity: MemoryEntity;
  active: boolean;
  onSelect: () => void;
  onRenamed: (newKey: string) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(entity.name);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    const next = name.trim();
    if (!next || next === entity.name) {
      setRenaming(false);
      setName(entity.name);
      return;
    }
    setBusy(true);
    try {
      const res = await renameMemoryEntity(entity.id, next);
      onRenamed(res.entity.key);
      setRenaming(false);
    } catch {
      setName(entity.name);
    } finally {
      setBusy(false);
    }
  };

  if (renaming) {
    return (
      <span className={`entity-chip editing${active ? " active" : ""}`}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
            if (e.key === "Escape") {
              setRenaming(false);
              setName(entity.name);
            }
          }}
          disabled={busy}
          autoFocus
          aria-label="Rename entity"
        />
        <button type="button" onClick={() => void save()} disabled={busy}>
          Save
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      className={`entity-chip${active ? " active" : ""}`}
      onClick={onSelect}
      onDoubleClick={(e) => {
        e.preventDefault();
        setRenaming(true);
      }}
      title="Click to filter · double-click to rename"
    >
      {entity.name}
      <span className="count">{entity.memoryCount ?? 0}</span>
    </button>
  );
}

function MemoryRow({
  memory,
  editing,
  onToggleEdit,
  onDelete,
  deleting,
  onEntityClick,
  onRelationsChanged,
  knownEntities,
}: {
  memory: Memory;
  editing: boolean;
  onToggleEdit: () => void;
  onDelete: () => void;
  deleting: boolean;
  onEntityClick: (key: string) => void;
  onRelationsChanged: () => void;
  knownEntities: MemoryEntity[];
}) {
  const [entities, setEntities] = useState<MemoryEntity[]>(memory.entities || []);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEntities(memory.entities || []);
  }, [memory.entities]);

  const linkedKeys = new Set(entities.map((e) => e.key));
  const suggestions = knownEntities.filter((e) => !linkedKeys.has(e.key)).slice(0, 8);

  const add = async (name: string) => {
    const next = name.trim();
    if (!next || busy) return;
    setBusy(true);
    try {
      const res = await addMemoryEntity(memory.id, next);
      setEntities(res.entities);
      setDraft("");
      onRelationsChanged();
    } finally {
      setBusy(false);
    }
  };

  const unlink = async (entityId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await removeMemoryEntity(memory.id, entityId);
      setEntities(res.entities);
      onRelationsChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`mem-row${editing ? " editing" : ""}`}>
      <div className="body">
        <div className="content">{memory.content}</div>
        {!editing ? (
          <div className="meta">
            {memory.source} · {new Date(memory.createdAt).toLocaleDateString()}
            {entities.map((e) => (
              <button
                key={e.id}
                type="button"
                className="entity-inline"
                onClick={() => onEntityClick(e.key)}
              >
                {e.name}
              </button>
            ))}
          </div>
        ) : (
          <div className="relation-editor">
            <div className="relation-tags">
              {entities.length === 0 && (
                <span className="relation-empty">No relationships yet</span>
              )}
              {entities.map((e) => (
                <span key={e.id} className="relation-tag">
                  {e.name}
                  <button
                    type="button"
                    aria-label={`Remove ${e.name}`}
                    onClick={() => void unlink(e.id)}
                    disabled={busy}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <form
              className="relation-add"
              onSubmit={(e) => {
                e.preventDefault();
                void add(draft);
              }}
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Add person, place, thing…"
                list={`entity-suggest-${memory.id}`}
                disabled={busy}
              />
              <datalist id={`entity-suggest-${memory.id}`}>
                {suggestions.map((s) => (
                  <option key={s.id} value={s.name} />
                ))}
              </datalist>
              <button type="submit" disabled={busy || !draft.trim()}>
                Add
              </button>
            </form>
          </div>
        )}
      </div>
      <div className="mem-actions">
        <button type="button" className="edit-rel" onClick={onToggleEdit}>
          {editing ? "Done" : "Edit"}
        </button>
        <button className="del" onClick={onDelete} disabled={deleting || editing}>
          {deleting ? "…" : "Delete"}
        </button>
      </div>
    </div>
  );
}
