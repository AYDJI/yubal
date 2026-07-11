import { api } from "./client";
import type { components } from "./schema";

export type LastFmSettings = components["schemas"]["LastFmSettingsResponse"];
export type DiscoverySuggestion =
  components["schemas"]["DiscoverySuggestionResponse"];
export type DiscoveryStats = components["schemas"]["DiscoveryStatsResponse"];

type ScanResult =
  | { success: true; newSuggestions: number; totalPending: number }
  | { success: false; error: string };

// --- Settings ---

export async function getSettings(): Promise<LastFmSettings | null> {
  const { data, error } = await api.GET("/discovery/settings");
  if (error) return null;
  return data;
}

export async function connectLastfm(
  username: string,
  apiKey: string,
): Promise<LastFmSettings | null> {
  const { data, error } = await api.POST("/discovery/connect", {
    body: { username, api_key: apiKey },
  });
  if (error) return null;
  return data;
}

export async function disconnectLastfm(): Promise<boolean> {
  const { error } = await api.POST("/discovery/disconnect");
  return !error;
}

export async function updateSettings(
  updates: Partial<LastFmSettings & { api_key?: string }>,
): Promise<LastFmSettings | null> {
  const { data, error } = await api.PUT("/discovery/settings", {
    body: updates as Record<string, unknown>,
  });
  if (error) return null;
  return data;
}

// --- Scan ---

export async function runScan(): Promise<ScanResult> {
  const { data, error } = await api.POST("/discovery/scan");
  if (error) {
    return { success: false, error: "Failed to run discovery scan" };
  }
  return {
    success: true,
    newSuggestions: data.new_suggestions,
    totalPending: data.total_pending,
  };
}

export async function generateSimilarTracksPlaylist(): Promise<ScanResult> {
  const { data, error } = await api.POST("/discovery/playlists/similar-tracks");
  if (error) {
    return {
      success: false,
      error: "Failed to generate similar tracks playlist",
    };
  }
  return {
    success: true,
    newSuggestions: data.new_suggestions,
    totalPending: data.total_pending,
  };
}

// --- Suggestions ---

export async function listSuggestions(
  status?: components["schemas"]["SuggestionStatus"] | null,
): Promise<DiscoverySuggestion[]> {
  const { data, error } = await api.GET("/discovery/suggestions", {
    params: { query: { status: status ?? null } },
  });
  if (error) return [];
  return data.items;
}

export async function approveSuggestion(
  id: string,
): Promise<DiscoverySuggestion | null> {
  const { data, error } = await api.POST(
    "/discovery/suggestions/{suggestion_id}/approve",
    { params: { path: { suggestion_id: id } } },
  );
  if (error) return null;
  return data;
}

export async function rejectSuggestion(id: string): Promise<boolean> {
  const { error } = await api.POST(
    "/discovery/suggestions/{suggestion_id}/reject",
    { params: { path: { suggestion_id: id } } },
  );
  return !error;
}

export async function bulkApprove(suggestionIds?: string[]): Promise<number> {
  const { data, error } = await api.POST(
    "/discovery/suggestions/bulk-approve",
    {
      body: { suggestion_ids: suggestionIds ?? null },
    },
  );
  if (error) return 0;
  return (data as Record<string, number>)?.approved ?? 0;
}

// --- Discover Playlist ---

type DiscoverPlaylistResult =
  | {
      success: true;
      approved: number;
      playlistTracks: number;
      playlistPath: string | null | undefined;
    }
  | { success: false; error: string };

export async function createDiscoverPlaylist(): Promise<DiscoverPlaylistResult> {
  const { data, error } = await api.POST("/discovery/playlists/discover");
  if (error) {
    return { success: false, error: "Failed to create Discover playlist" };
  }
  return {
    success: true,
    approved: data.approved,
    playlistTracks: data.playlist_tracks,
    playlistPath: data.playlist_path,
  };
}

// --- Clear ---

export async function clearSuggestions(): Promise<number> {
  const { data, error } = await api.POST("/discovery/suggestions/clear");
  if (error) return 0;
  return (data as Record<string, number>)?.cleared ?? 0;
}

// --- Stats ---

export async function getStats(): Promise<DiscoveryStats | null> {
  const { data, error } = await api.GET("/discovery/stats");
  if (error) return null;
  return data;
}
