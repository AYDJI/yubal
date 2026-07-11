import {
  approveSuggestion,
  bulkApprove,
  connectLastfm,
  createDiscoverPlaylist,
  disconnectLastfm,
  generateSimilarTracksPlaylist,
  getSettings,
  getStats,
  listSuggestions,
  rejectSuggestion,
  runScan,
  updateSettings,
  type DiscoverySuggestion,
  type DiscoveryStats,
  type LastFmSettings,
} from "@/api/discovery";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { useCallback, useEffect, useState } from "react";

export interface UseDiscoveryResult {
  settings: LastFmSettings | null;
  suggestions: DiscoverySuggestion[];
  stats: DiscoveryStats | null;
  isLoading: boolean;
  isScanning: boolean;
  isGeneratingPlaylist: boolean;
  isCreatingPlaylist: boolean;
  connect: (username: string, apiKey: string) => Promise<boolean>;
  disconnect: () => Promise<void>;
  update: (updates: Partial<LastFmSettings>) => Promise<void>;
  scan: () => Promise<void>;
  approve: (id: string) => Promise<void>;
  reject: (id: string) => Promise<void>;
  approveAll: () => Promise<void>;
  generateSimilarTracks: () => Promise<void>;
  createPlaylist: () => Promise<void>;
}

export function useDiscovery(): UseDiscoveryResult {
  const [settings, setSettings] = useState<LastFmSettings | null>(null);
  const [suggestions, setSuggestions] = useState<DiscoverySuggestion[]>([]);
  const [stats, setStats] = useState<DiscoveryStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [isGeneratingPlaylist, setIsGeneratingPlaylist] = useState(false);
  const [isCreatingPlaylist, setIsCreatingPlaylist] = useState(false);

  const fetchAll = useCallback(async () => {
    const [settingsData, suggestionsData, statsData] = await Promise.all([
      getSettings(),
      listSuggestions(),
      getStats(),
    ]);
    setSettings(settingsData);
    setSuggestions(suggestionsData);
    setStats(statsData);
  }, []);

  const connect = useCallback(
    async (username: string, apiKey: string): Promise<boolean> => {
      const result = await connectLastfm(username, apiKey);
      if (!result) {
        showErrorToast(
          "Connection failed",
          "Could not connect Last.fm account",
        );
        return false;
      }
      setSettings(result);
      showSuccessToast("Connected", "Last.fm account connected");
      return true;
    },
    [],
  );

  const disconnect = useCallback(async () => {
    const success = await disconnectLastfm();
    if (!success) {
      showErrorToast("Disconnect failed", "Could not disconnect Last.fm");
      return;
    }
    setSettings(null);
    setSuggestions([]);
    showSuccessToast("Disconnected", "Last.fm account disconnected");
  }, []);

  const update = useCallback(async (updates: Partial<LastFmSettings>) => {
    const result = await updateSettings(updates);
    if (result) {
      setSettings(result);
      showSuccessToast("Settings saved", "Discovery settings updated");
    }
  }, []);

  const scan = useCallback(async () => {
    setIsScanning(true);
    const result = await runScan();
    setIsScanning(false);
    if (!result.success) {
      showErrorToast("Scan failed", result.error);
      return;
    }
    await fetchAll();
    showSuccessToast(
      "Scan complete",
      `Found ${result.newSuggestions} new suggestions`,
    );
  }, [fetchAll]);

  const approve = useCallback(
    async (id: string) => {
      const result = await approveSuggestion(id);
      if (!result) {
        showErrorToast("Approve failed", "Could not approve suggestion");
        return;
      }
      await fetchAll();
      showSuccessToast("Approved", "Download job queued");
    },
    [fetchAll],
  );

  const reject = useCallback(
    async (id: string) => {
      const success = await rejectSuggestion(id);
      if (!success) {
        showErrorToast("Reject failed", "Could not reject suggestion");
        return;
      }
      await fetchAll();
    },
    [fetchAll],
  );

  const approveAll = useCallback(async () => {
    const count = await bulkApprove();
    if (count > 0) {
      await fetchAll();
      showSuccessToast("Approved", `${count} suggestions approved`);
    }
  }, [fetchAll]);

  const generateSimilarTracks = useCallback(async () => {
    setIsGeneratingPlaylist(true);
    const result = await generateSimilarTracksPlaylist();
    setIsGeneratingPlaylist(false);
    if (!result.success) {
      showErrorToast(
        "Failed to generate playlist",
        "Could not generate similar tracks playlist",
      );
      return;
    }
    if (result.newSuggestions > 0) {
      await fetchAll();
      showSuccessToast(
        "Playlist generated",
        `Found ${result.newSuggestions} similar tracks`,
      );
    } else {
      showErrorToast(
        "No new tracks",
        "No similar tracks found above the confidence threshold",
      );
    }
  }, [fetchAll]);

  const createPlaylist = useCallback(async () => {
    setIsCreatingPlaylist(true);
    const result = await createDiscoverPlaylist();
    setIsCreatingPlaylist(false);
    if (!result.success) {
      showErrorToast("Playlist failed", "Could not create Discover playlist");
      return;
    }
    await fetchAll();
    if (result.playlistTracks > 0) {
      showSuccessToast(
        "Discover playlist created",
        `${result.approved} approved, ${result.playlistTracks} tracks in playlist`,
      );
    } else if (result.approved > 0) {
      showSuccessToast(
        "Approved",
        `${result.approved} approved — playlist will populate as downloads complete`,
      );
    } else {
      showSuccessToast(
        "Discover playlist updated",
        "No downloaded tracks found yet. Run scan + approve first.",
      );
    }
  }, [fetchAll]);

  useEffect(() => {
    let mounted = true;
    async function init() {
      try {
        await fetchAll();
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    init();
    return () => {
      mounted = false;
    };
  }, [fetchAll]);

  return {
    settings,
    suggestions,
    stats,
    isLoading,
    isScanning,
    isGeneratingPlaylist,
    isCreatingPlaylist,
    connect,
    disconnect,
    update,
    scan,
    approve,
    reject,
    approveAll,
    generateSimilarTracks,
    createPlaylist,
  };
}
