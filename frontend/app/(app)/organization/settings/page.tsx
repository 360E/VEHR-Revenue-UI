"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";

type OrganizationTile = {
  id: string;
  title: string;
  icon: string;
  category: string;
  link_type: "internal_route" | "external_url";
  href: string;
  sort_order: number;
  required_permissions: string[];
  is_active: boolean;
};

type Announcement = {
  id: string;
  title: string;
  body: string;
  start_date: string;
  end_date?: string | null;
  is_active: boolean;
  created_at: string;
};

type UserRecord = {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  is_active: boolean;
};

type InviteRecord = {
  id: string;
  email: string;
  allowed_roles: string[];
  status: string;
  expires_at: string;
  accepted_at?: string | null;
};

type TileDraft = {
  title: string;
  category: string;
  href: string;
  required_permissions: string;
};

const LOW_RISK_ROLES = ["Counselor", "Case Manager"] as const;

function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function parsePermissionList(input: string) {
  return input
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export default function OrganizationSettingsPage() {
  const [tiles, setTiles] = useState<OrganizationTile[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [invites, setInvites] = useState<InviteRecord[]>([]);
  const [tileDrafts, setTileDrafts] = useState<Record<string, TileDraft>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [usersSectionError, setUsersSectionError] = useState<string | null>(null);

  const [tileForm, setTileForm] = useState({
    title: "",
    icon: "layers",
    category: "Clinical Ops",
    link_type: "internal_route" as "internal_route" | "external_url",
    href: "/organization/home",
    required_permissions: "patients:read",
    is_active: true,
  });

  const [announcementForm, setAnnouncementForm] = useState({
    title: "",
    body: "",
    start_date: new Date().toISOString().slice(0, 10),
    end_date: "",
    is_active: true,
  });

  const [inviteForm, setInviteForm] = useState({
    email: "",
    counselor: true,
    caseManager: true,
  });

  const orderedTileIds = useMemo(
    () => [...tiles].sort((a, b) => a.sort_order - b.sort_order).map((tile) => tile.id),
    [tiles],
  );

  async function refresh() {
    try {
      setLoading(true);
      setError(null);
      setUsersSectionError(null);

      const [tileResult, announcementResult, usersResult, invitesResult] = await Promise.allSettled([
        apiFetch<OrganizationTile[]>("/api/v1/organization/tiles?include_inactive=true&for_settings=true", { cache: "no-store" }),
        apiFetch<Announcement[]>("/api/v1/organization/announcements?include_inactive=true&for_settings=true", { cache: "no-store" }),
        apiFetch<UserRecord[]>("/api/v1/users", { cache: "no-store" }),
        apiFetch<InviteRecord[]>("/api/v1/admin/invites", { cache: "no-store" }),
      ]);

      if (tileResult.status === "rejected") {
        throw tileResult.reason;
      }
      if (announcementResult.status === "rejected") {
        throw announcementResult.reason;
      }

      const sortedTiles = tileResult.value.sort((a, b) => a.sort_order - b.sort_order);
      setTiles(sortedTiles);
      setTileDrafts(
        Object.fromEntries(
          sortedTiles.map((tile) => [
            tile.id,
            {
              title: tile.title,
              category: tile.category,
              href: tile.href,
              required_permissions: tile.required_permissions.join(", "),
            },
          ]),
        ),
      );
      setAnnouncements(announcementResult.value);

      if (usersResult.status === "fulfilled") {
        setUsers(usersResult.value);
      } else {
        setUsers([]);
        setUsersSectionError(toErrorMessage(usersResult.reason, "Failed to load users."));
      }

      if (invitesResult.status === "fulfilled") {
        setInvites(invitesResult.value);
      } else {
        setInvites([]);
        setUsersSectionError((existing) => existing || toErrorMessage(invitesResult.reason, "Failed to load invites."));
      }
    } catch (loadError) {
      setError(toErrorMessage(loadError, "Failed to load organization settings"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function createTile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setError(null);
      await apiFetch("/api/v1/organization/tiles", {
        method: "POST",
        body: JSON.stringify({
          ...tileForm,
          required_permissions: parsePermissionList(tileForm.required_permissions),
          sort_order: (tiles.at(-1)?.sort_order ?? 0) + 10,
        }),
      });
      setTileForm((current) => ({ ...current, title: "", href: "/organization/home" }));
      await refresh();
    } catch (createError) {
      setError(toErrorMessage(createError, "Failed to create tile"));
    }
  }

  async function updateTile(tile: OrganizationTile, patch: Partial<OrganizationTile>) {
    try {
      setError(null);
      await apiFetch(`/api/v1/organization/tiles/${tile.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      await refresh();
    } catch (updateError) {
      setError(toErrorMessage(updateError, "Failed to update tile"));
    }
  }

  function updateTileDraft(tileId: string, patch: Partial<TileDraft>) {
    setTileDrafts((current) => {
      const existing = current[tileId];
      if (!existing) return current;
      return { ...current, [tileId]: { ...existing, ...patch } };
    });
  }

  async function saveTile(tile: OrganizationTile) {
    const draft = tileDrafts[tile.id];
    if (!draft) return;
    await updateTile(tile, {
      title: draft.title.trim(),
      category: draft.category.trim(),
      href: draft.href.trim(),
      required_permissions: parsePermissionList(draft.required_permissions),
    });
  }

  async function moveTile(tileId: string, direction: -1 | 1) {
    const current = [...orderedTileIds];
    const index = current.findIndex((id) => id === tileId);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= current.length) return;
    const swapped = [...current];
    const [target] = swapped.splice(index, 1);
    swapped.splice(nextIndex, 0, target);
    try {
      setError(null);
      await apiFetch("/api/v1/organization/tiles/reorder", {
        method: "POST",
        body: JSON.stringify({ ordered_ids: swapped }),
      });
      await refresh();
    } catch (reorderError) {
      setError(toErrorMessage(reorderError, "Failed to reorder tiles"));
    }
  }

  async function createAnnouncement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setError(null);
      await apiFetch("/api/v1/organization/announcements", {
        method: "POST",
        body: JSON.stringify({
          title: announcementForm.title,
          body: announcementForm.body,
          start_date: announcementForm.start_date,
          end_date: announcementForm.end_date || null,
          is_active: announcementForm.is_active,
        }),
      });
      setAnnouncementForm((current) => ({ ...current, title: "", body: "" }));
      await refresh();
    } catch (createError) {
      setError(toErrorMessage(createError, "Failed to create announcement"));
    }
  }

  async function toggleAnnouncement(announcement: Announcement) {
    try {
      setError(null);
      await apiFetch(`/api/v1/organization/announcements/${announcement.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !announcement.is_active }),
      });
      await refresh();
    } catch (updateError) {
      setError(toErrorMessage(updateError, "Failed to update announcement"));
    }
  }

  async function createInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setError(null);
      setNotice(null);
      setUsersSectionError(null);

      const allowedRoles = LOW_RISK_ROLES.filter((role) => {
        if (role === "Counselor") return inviteForm.counselor;
        return inviteForm.caseManager;
      });

      if (allowedRoles.length === 0) {
        setUsersSectionError("Select at least one allowed role for this invite.");
        return;
      }

      await apiFetch<InviteRecord>("/api/v1/admin/invites", {
        method: "POST",
        body: JSON.stringify({
          email: inviteForm.email.trim().toLowerCase(),
          allowed_roles: allowedRoles,
        }),
      });
      setInviteForm({ email: "", counselor: true, caseManager: true });
      setNotice("Invite sent. The user will receive an email with an acceptance link.");
      await refresh();
    } catch (inviteError) {
      setUsersSectionError(toErrorMessage(inviteError, "Failed to send invite."));
    }
  }

  async function resendInvite(inviteId: string) {
    try {
      setUsersSectionError(null);
      setNotice(null);
      await apiFetch<InviteRecord>(`/api/v1/admin/invites/${inviteId}/resend`, {
        method: "POST",
      });
      setNotice("Invite resent.");
      await refresh();
    } catch (resendError) {
      setUsersSectionError(toErrorMessage(resendError, "Failed to resend invite."));
    }
  }

  async function revokeInvite(inviteId: string) {
    try {
      setUsersSectionError(null);
      setNotice(null);
      await apiFetch<InviteRecord>(`/api/v1/admin/invites/${inviteId}/revoke`, {
        method: "POST",
      });
      setNotice("Invite revoked.");
      await refresh();
    } catch (revokeError) {
      setUsersSectionError(toErrorMessage(revokeError, "Failed to revoke invite."));
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">Organization</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">Manage users, tiles, permissions, and announcements.</p>
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      ) : null}

      {notice ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</div>
      ) : null}

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base">Users</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <form className="grid gap-3 lg:grid-cols-2" onSubmit={createInvite}>
            <Input
              className="lg:col-span-2"
              placeholder="Invite email"
              type="email"
              value={inviteForm.email}
              onChange={(event) => setInviteForm((current) => ({ ...current, email: event.target.value }))}
              required
            />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={inviteForm.counselor}
                onChange={(event) => setInviteForm((current) => ({ ...current, counselor: event.target.checked }))}
              />
              Counselor
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={inviteForm.caseManager}
                onChange={(event) => setInviteForm((current) => ({ ...current, caseManager: event.target.checked }))}
              />
              Case Manager
            </label>
            <div className="lg:col-span-2">
              <Button type="submit">Send Invite</Button>
            </div>
          </form>

          {usersSectionError ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {usersSectionError}
            </div>
          ) : null}

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Organization Users</h3>
            {loading ? <div className="text-sm text-slate-600">Loading users...</div> : null}
            {!loading && users.length === 0 ? <div className="text-sm text-slate-600">No users found.</div> : null}
            {users.map((user) => (
              <div key={user.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="font-semibold text-slate-900">{user.full_name || user.email}</div>
                <div className="text-slate-600">{user.email}</div>
                <div className="mt-1 text-xs text-slate-500">
                  {user.role} | {user.is_active ? "active" : "inactive"}
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">Invites</h3>
            {!loading && invites.length === 0 ? <div className="text-sm text-slate-600">No invites yet.</div> : null}
            {invites.map((invite) => (
              <div key={invite.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-semibold text-slate-900">{invite.email}</div>
                    <div className="text-xs text-slate-500">
                      Roles: {invite.allowed_roles.join(", ")} | Status: {invite.status}
                    </div>
                    <div className="text-xs text-slate-500">Expires: {formatDateTime(invite.expires_at)}</div>
                    {invite.accepted_at ? (
                      <div className="text-xs text-slate-500">Accepted: {formatDateTime(invite.accepted_at)}</div>
                    ) : null}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => resendInvite(invite.id)}
                      disabled={invite.status === "accepted" || invite.status === "revoked"}
                    >
                      Resend
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => revokeInvite(invite.id)}
                      disabled={invite.status === "accepted" || invite.status === "revoked"}
                    >
                      Revoke
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base">Create Tile</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          <form className="grid gap-3 lg:grid-cols-2" onSubmit={createTile}>
            <Input placeholder="Tile title" value={tileForm.title} onChange={(e) => setTileForm((c) => ({ ...c, title: e.target.value }))} required />
            <Input placeholder="Icon key" value={tileForm.icon} onChange={(e) => setTileForm((c) => ({ ...c, icon: e.target.value }))} required />
            <Input placeholder="Category" value={tileForm.category} onChange={(e) => setTileForm((c) => ({ ...c, category: e.target.value }))} required />
            <select className="h-9 rounded-md border border-slate-200 px-3 text-sm" value={tileForm.link_type} onChange={(e) => setTileForm((c) => ({ ...c, link_type: e.target.value as "internal_route" | "external_url" }))}>
              <option value="internal_route">internal_route</option>
              <option value="external_url">external_url</option>
            </select>
            <Input className="lg:col-span-2" placeholder="href" value={tileForm.href} onChange={(e) => setTileForm((c) => ({ ...c, href: e.target.value }))} required />
            <Input className="lg:col-span-2" placeholder="required permissions, comma-separated" value={tileForm.required_permissions} onChange={(e) => setTileForm((c) => ({ ...c, required_permissions: e.target.value }))} />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={tileForm.is_active} onChange={(e) => setTileForm((c) => ({ ...c, is_active: e.target.checked }))} />
              Active
            </label>
            <div className="lg:col-span-2">
              <Button type="submit">Create Tile</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base">Tiles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-5">
          {loading ? <div className="text-sm text-slate-600">Loading tiles...</div> : null}
          {tiles.map((tile, index) => (
            <div key={tile.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-900">{tile.title}</div>
                <div className="flex gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => moveTile(tile.id, -1)} disabled={index === 0}>Up</Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => moveTile(tile.id, 1)} disabled={index === tiles.length - 1}>Down</Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => updateTile(tile, { is_active: !tile.is_active })}>
                    {tile.is_active ? "Disable" : "Enable"}
                  </Button>
                </div>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                {tile.category} | {tile.link_type} | {tile.href}
              </div>
              <div className="mt-1 text-xs text-slate-500">Required: {tile.required_permissions.join(", ") || "none"}</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <Input
                  value={tileDrafts[tile.id]?.title ?? tile.title}
                  onChange={(event) => updateTileDraft(tile.id, { title: event.target.value })}
                  placeholder="Title"
                />
                <Input
                  value={tileDrafts[tile.id]?.category ?? tile.category}
                  onChange={(event) => updateTileDraft(tile.id, { category: event.target.value })}
                  placeholder="Category"
                />
                <Input
                  className="sm:col-span-2"
                  value={tileDrafts[tile.id]?.href ?? tile.href}
                  onChange={(event) => updateTileDraft(tile.id, { href: event.target.value })}
                  placeholder="Href"
                />
                <Input
                  className="sm:col-span-2"
                  value={tileDrafts[tile.id]?.required_permissions ?? tile.required_permissions.join(", ")}
                  onChange={(event) => updateTileDraft(tile.id, { required_permissions: event.target.value })}
                  placeholder="Required permissions, comma-separated"
                />
                <div className="sm:col-span-2">
                  <Button type="button" size="sm" onClick={() => saveTile(tile)}>
                    Save Tile Changes
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base">Create Announcement</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          <form className="grid gap-3" onSubmit={createAnnouncement}>
            <Input placeholder="Title" value={announcementForm.title} onChange={(e) => setAnnouncementForm((c) => ({ ...c, title: e.target.value }))} required />
            <textarea className="min-h-[120px] rounded-md border border-slate-200 px-3 py-2 text-sm" placeholder="Body (rich text/plain)" value={announcementForm.body} onChange={(e) => setAnnouncementForm((c) => ({ ...c, body: e.target.value }))} required />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input type="date" value={announcementForm.start_date} onChange={(e) => setAnnouncementForm((c) => ({ ...c, start_date: e.target.value }))} required />
              <Input type="date" value={announcementForm.end_date} onChange={(e) => setAnnouncementForm((c) => ({ ...c, end_date: e.target.value }))} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={announcementForm.is_active} onChange={(e) => setAnnouncementForm((c) => ({ ...c, is_active: e.target.checked }))} />
              Active
            </label>
            <Button type="submit">Create Announcement</Button>
          </form>
        </CardContent>
      </Card>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base">Announcements</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-5">
          {announcements.map((announcement) => (
            <div key={announcement.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-semibold text-slate-900">{announcement.title}</div>
                <Button type="button" size="sm" variant="outline" onClick={() => toggleAnnouncement(announcement)}>
                  {announcement.is_active ? "Disable" : "Enable"}
                </Button>
              </div>
              <div className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{announcement.body}</div>
              <div className="mt-1 text-xs text-slate-500">
                {announcement.start_date} - {announcement.end_date || "open-ended"}
              </div>
            </div>
          ))}
          {announcements.length === 0 ? <div className="text-sm text-slate-600">No announcements yet.</div> : null}
        </CardContent>
      </Card>
    </div>
  );
}
