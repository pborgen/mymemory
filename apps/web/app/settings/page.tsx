"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  deleteAllMemories,
  exportMemoriesJson,
  fetchReminders,
  fetchSettings,
  importMemoriesText,
  markReminderDone,
  pasteInbox,
  updateSettings,
} from "@/api";
import { AppBar } from "@/AppBar";
import { useAuth } from "@/auth";
import type { FeatureCatalogItem, FeatureFlag, UserSettings } from "@/types";

const GROUP_BLURBS: Record<string, string> = {
  Looking: "What shows up in chat and on your Memories list.",
  "Smart chat": "How MyMemory understands edits, forgets, and answers.",
  Library: "Bring facts in, export them, or park follow-ups.",
  Devices: "Voice and Apple extras — keep off unless you need them.",
};

const DEFAULT_GROUP_ORDER = ["Looking", "Smart chat", "Library", "Devices"];

function buildGroups(
  catalog: FeatureCatalogItem[],
  order: string[],
): [string, FeatureCatalogItem[]][] {
  const map = new Map<string, FeatureCatalogItem[]>();
  for (const item of catalog) {
    const list = map.get(item.group) ?? [];
    list.push(item);
    map.set(item.group, list);
  }
  const known = order.filter((g) => map.has(g));
  const extras = [...map.keys()].filter((g) => !order.includes(g)).sort();
  return [...known, ...extras].map((g) => [g, map.get(g) ?? []]);
}

function subgroupBlocks(
  items: FeatureCatalogItem[],
): { title: string | null; items: FeatureCatalogItem[] }[] {
  const blocks: { title: string | null; items: FeatureCatalogItem[] }[] = [];
  for (const item of items) {
    const title = item.subgroup?.trim() || null;
    const last = blocks[blocks.length - 1];
    if (last && last.title === title) {
      last.items.push(item);
    } else {
      blocks.push({ title, items: [item] });
    }
  }
  return blocks;
}

export default function SettingsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const queryClient = useQueryClient();
  const [pasteText, setPasteText] = useState("");
  const [importText, setImportText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [activeGroup, setActiveGroup] = useState<string>("Looking");

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace("/login");
  }, [isLoading, isAuthenticated, router]);

  const { data, isLoading: settingsLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: isAuthenticated,
  });

  const settings = data?.settings;
  const catalog = data?.catalog ?? [];
  const groupOrder = data?.groups?.length
    ? data.groups
    : data?.groupOrder?.length
      ? data.groupOrder
      : DEFAULT_GROUP_ORDER;

  const groups = useMemo(
    () => buildGroups(catalog, groupOrder),
    [catalog, groupOrder],
  );

  const enabledCount = useMemo(() => {
    if (!settings) return 0;
    return Object.values(settings).filter(Boolean).length;
  }, [settings]);

  const save = useMutation({
    mutationFn: (patch: Partial<UserSettings>) => updateSettings(patch),
    onSuccess: (res) => {
      queryClient.setQueryData(["settings"], res);
      setStatus("Synced");
      window.setTimeout(() => setStatus(null), 1600);
    },
    onError: (e: Error) => setStatus(e.message),
  });

  const remindersQuery = useQuery({
    queryKey: ["reminders"],
    queryFn: fetchReminders,
    enabled: !!settings?.reminders && isAuthenticated,
  });

  useEffect(() => {
    if (groups.length && !groups.some(([g]) => g === activeGroup)) {
      setActiveGroup(groups[0][0]);
    }
  }, [groups, activeGroup]);

  if (isLoading || !isAuthenticated || settingsLoading || !settings) {
    return (
      <div className="app-shell">
        <div className="fill-center">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  const toggle = (key: FeatureFlag) => {
    save.mutate({ [key]: !settings[key] });
  };

  const activeItems = groups.find(([g]) => g === activeGroup)?.[1] ?? [];
  const blocks = subgroupBlocks(activeItems);

  return (
    <div className="app-shell">
      <AppBar active="settings" />
      <div className="settings-stage">
        <div className="settings-aurora" aria-hidden="true" />
        <div className="container settings-hero">
          <p className="settings-brand">MyMemory</p>
          <h1 className="settings-title">
            Dial in
            <span className="settings-title-accent"> what stays quiet.</span>
          </h1>
          <p className="settings-lead">
            Features stay off until you want them — chat stays clean by default.
          </p>
          <div className="settings-meter" aria-live="polite">
            <span className="settings-meter-track">
              <span
                className="settings-meter-fill"
                style={{
                  width: `${Math.min(
                    100,
                    (enabledCount / Math.max(1, Object.keys(settings).length)) * 100,
                  )}%`,
                }}
              />
            </span>
            <span className="settings-meter-label">
              {enabledCount} live
              {status ? <em className="settings-status"> · {status}</em> : null}
            </span>
          </div>
        </div>
      </div>

      <div className="container settings-board">
        <nav className="settings-rail" aria-label="Settings groups">
          {groups.map(([group, items], index) => {
            const onCount = items.filter((i) => settings[i.key]).length;
            return (
              <button
                key={group}
                type="button"
                className={`settings-rail-item ${activeGroup === group ? "active" : ""}`}
                onClick={() => setActiveGroup(group)}
              >
                <span className="settings-rail-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="settings-rail-copy">
                  <span className="settings-rail-name">{group}</span>
                  <span className="settings-rail-meta">
                    {onCount}/{items.length} on
                  </span>
                </span>
              </button>
            );
          })}
        </nav>

        <div className="settings-panel" key={activeGroup}>
          <header className="settings-panel-head">
            <h2>{activeGroup}</h2>
            <p>{GROUP_BLURBS[activeGroup] ?? "Optional capabilities for this area."}</p>
          </header>

          {blocks.map((block) => (
            <div key={block.title ?? "default"} className="settings-subgroup">
              {block.title ? (
                <h3 className="settings-subgroup-title">{block.title}</h3>
              ) : null}
              <ul className="settings-list">
                {block.items.map((item, i) => {
                  const on = settings[item.key];
                  return (
                    <li
                      key={item.key}
                      className={`settings-row ${on ? "is-on" : ""}`}
                      style={{ animationDelay: `${i * 45}ms` }}
                    >
                      <div className="settings-row-text">
                        <div className="settings-name">{item.name}</div>
                        <div className="settings-desc">{item.description}</div>
                      </div>
                      <button
                        type="button"
                        className={`settings-switch ${on ? "on" : ""}`}
                        aria-pressed={on}
                        aria-label={`${item.name}: ${on ? "on" : "off"}`}
                        onClick={() => toggle(item.key)}
                      >
                        <span className="settings-switch-knob" />
                        <span className="settings-switch-label">
                          {on ? "On" : "Off"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}

          {activeGroup === "Library" && settings.pasteInbox ? (
            <div className="settings-tool">
              <h3>Paste inbox</h3>
              <textarea
                className="settings-textarea"
                rows={5}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder="One fact per line…"
              />
              <button
                type="button"
                className="settings-action"
                onClick={async () => {
                  try {
                    const res = await pasteInbox(pasteText);
                    setPasteText("");
                    setStatus(`Saved ${res.count}`);
                    queryClient.invalidateQueries({ queryKey: ["memories"] });
                  } catch (e) {
                    setStatus(e instanceof Error ? e.message : "Paste failed");
                  }
                }}
              >
                Save lines
              </button>
            </div>
          ) : null}

          {activeGroup === "Library" && settings.importExport ? (
            <div className="settings-tool">
              <h3>Import / export</h3>
              <div className="settings-actions">
                <button
                  type="button"
                  className="settings-action"
                  onClick={async () => {
                    try {
                      const data = await exportMemoriesJson();
                      const blob = new Blob([JSON.stringify(data, null, 2)], {
                        type: "application/json",
                      });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "mymemory-export.json";
                      a.click();
                      URL.revokeObjectURL(url);
                      setStatus(`Exported ${data.count}`);
                    } catch (e) {
                      setStatus(e instanceof Error ? e.message : "Export failed");
                    }
                  }}
                >
                  Download JSON
                </button>
                <button
                  type="button"
                  className="settings-action danger"
                  onClick={async () => {
                    if (
                      !window.confirm(
                        "Delete ALL memories? This cannot be undone easily.",
                      )
                    ) {
                      return;
                    }
                    try {
                      const res = await deleteAllMemories();
                      setStatus(`Deleted ${res.deleted}`);
                      queryClient.invalidateQueries({ queryKey: ["memories"] });
                    } catch (e) {
                      setStatus(e instanceof Error ? e.message : "Delete failed");
                    }
                  }}
                >
                  Delete all
                </button>
              </div>
              <textarea
                className="settings-textarea"
                rows={4}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder="Paste CSV or one fact per line…"
              />
              <button
                type="button"
                className="settings-action"
                onClick={async () => {
                  try {
                    const res = await importMemoriesText(importText);
                    setImportText("");
                    setStatus(`Imported ${res.count}`);
                    queryClient.invalidateQueries({ queryKey: ["memories"] });
                  } catch (e) {
                    setStatus(e instanceof Error ? e.message : "Import failed");
                  }
                }}
              >
                Import
              </button>
            </div>
          ) : null}

          {activeGroup === "Library" && settings.reminders ? (
            <div className="settings-tool">
              <h3>Reminders</h3>
              <p className="settings-desc">
                In chat: “remind me to call the lender tomorrow”.
              </p>
              <ul className="settings-reminders">
                {(remindersQuery.data ?? []).map((r) => (
                  <li key={r.id}>
                    <span>{r.content}</span>
                    <button
                      type="button"
                      className="settings-action"
                      onClick={async () => {
                        await markReminderDone(r.id);
                        queryClient.invalidateQueries({ queryKey: ["reminders"] });
                      }}
                    >
                      Done
                    </button>
                  </li>
                ))}
              </ul>
              {(remindersQuery.data ?? []).length === 0 ? (
                <p className="settings-desc">No open reminders.</p>
              ) : null}
            </div>
          ) : null}

          {activeGroup === "Devices" && settings.iosIntegrations ? (
            <div className="settings-tool">
              <h3>iOS tips</h3>
              <p className="settings-desc">
                Deep link <code>mymemory://chat</code> — wire a Shortcut or Siri phrase
                that opens Chat with a dictated fact.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
