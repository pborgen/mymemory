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
import type { FeatureFlag, UserSettings } from "@/types";

export default function SettingsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const queryClient = useQueryClient();
  const [pasteText, setPasteText] = useState("");
  const [importText, setImportText] = useState("");
  const [status, setStatus] = useState<string | null>(null);

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

  const groups = useMemo(() => {
    const map = new Map<string, typeof catalog>();
    for (const item of catalog) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return [...map.entries()];
  }, [catalog]);

  const save = useMutation({
    mutationFn: (patch: Partial<UserSettings>) => updateSettings(patch),
    onSuccess: (res) => {
      queryClient.setQueryData(["settings"], res);
      setStatus("Saved");
    },
    onError: (e: Error) => setStatus(e.message),
  });

  const remindersQuery = useQuery({
    queryKey: ["reminders"],
    queryFn: fetchReminders,
    enabled: !!settings?.reminders && isAuthenticated,
  });

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

  return (
    <div className="app-shell">
      <AppBar active="settings" />
      <div className="container settings-wrap">
        <h1 className="settings-title">Settings</h1>
        <p className="settings-lead">
          Turn features on only when you want them — chat stays quiet by default.
        </p>
        {status ? <p className="settings-status">{status}</p> : null}

        {groups.map(([group, items]) => (
          <section key={group} className="settings-group">
            <h2>{group}</h2>
            <ul className="settings-list">
              {items.map((item) => (
                <li key={item.key}>
                  <div>
                    <div className="settings-name">{item.name}</div>
                    <div className="settings-desc">{item.description}</div>
                  </div>
                  <button
                    type="button"
                    className={`settings-toggle ${settings[item.key] ? "on" : ""}`}
                    aria-pressed={settings[item.key]}
                    onClick={() => toggle(item.key)}
                  >
                    {settings[item.key] ? "On" : "Off"}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {settings.pasteInbox ? (
          <section className="settings-group">
            <h2>Paste inbox</h2>
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
                  setStatus(`Saved ${res.count} memories`);
                  queryClient.invalidateQueries({ queryKey: ["memories"] });
                } catch (e) {
                  setStatus(e instanceof Error ? e.message : "Paste failed");
                }
              }}
            >
              Save lines
            </button>
          </section>
        ) : null}

        {settings.importExport ? (
          <section className="settings-group">
            <h2>Import / export</h2>
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
                    setStatus(`Exported ${data.count} memories`);
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
                  if (!window.confirm("Delete ALL memories? This cannot be undone easily.")) {
                    return;
                  }
                  try {
                    const res = await deleteAllMemories();
                    setStatus(`Deleted ${res.deleted} memories`);
                    queryClient.invalidateQueries({ queryKey: ["memories"] });
                  } catch (e) {
                    setStatus(e instanceof Error ? e.message : "Delete failed");
                  }
                }}
              >
                Delete all memories
              </button>
            </div>
            <textarea
              className="settings-textarea"
              rows={4}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder="Paste CSV or one fact per line to import…"
            />
            <button
              type="button"
              className="settings-action"
              onClick={async () => {
                try {
                  const res = await importMemoriesText(importText);
                  setImportText("");
                  setStatus(`Imported ${res.count} memories`);
                  queryClient.invalidateQueries({ queryKey: ["memories"] });
                } catch (e) {
                  setStatus(e instanceof Error ? e.message : "Import failed");
                }
              }}
            >
              Import
            </button>
          </section>
        ) : null}

        {settings.reminders ? (
          <section className="settings-group">
            <h2>Reminders</h2>
            <p className="settings-desc">
              In chat: “remind me to call the lender tomorrow”.
            </p>
            <ul className="settings-list">
              {(remindersQuery.data ?? []).map((r) => (
                <li key={r.id}>
                  <div>
                    <div className="settings-name">{r.content}</div>
                  </div>
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
          </section>
        ) : null}

        {settings.iosIntegrations ? (
          <section className="settings-group">
            <h2>iOS tips</h2>
            <p className="settings-desc">
              Shortcuts deep link: <code>mymemory://chat</code>. Add a Shortcut that
              opens the app and dictates a fact, or pin a Reminders-style widget that
              jumps into Chat. Siri: create a Shortcut phrase like “Remember this”
              that opens MyMemory with the clipboard.
            </p>
          </section>
        ) : null}
      </div>
    </div>
  );
}
