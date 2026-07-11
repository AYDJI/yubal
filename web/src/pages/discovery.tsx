import { useDiscovery } from "@/features/discovery/use-discovery";
import {
  Button,
  Card,
  CardBody,
  Chip,
  Input,
  Switch,
  Tooltip,
} from "@heroui/react";
import {
  CircleCheckIcon,
  CircleXIcon,
  Disc3Icon,
  ListMusicIcon,
  ListPlusIcon,
  ScanIcon,
  SparklesIcon,
  Trash2Icon,
  UserIcon,
  KeyIcon,
} from "lucide-react";
import { useState } from "react";

export function DiscoveryPage() {
  const {
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
    clearAll,
    isClearing,
  } = useDiscovery();

  const [username, setUsername] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);

  const pendingSuggestions = suggestions.filter((s) => s.status === "pending");

  const handleConnect = async () => {
    if (!username || !apiKey) return;
    setIsConnecting(true);
    await connect(username, apiKey);
    setIsConnecting(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Disc3Icon className="text-primary h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!settings) {
    return (
      <>
        <h1 className="text-foreground mb-6 text-2xl font-bold">Discovery</h1>
        <Card>
          <CardBody className="gap-4 p-6">
            <div className="mb-2 flex items-center gap-3">
              <SparklesIcon className="text-primary h-6 w-6" />
              <h2 className="text-lg font-semibold">Connect Last.fm</h2>
            </div>
            <p className="text-foreground-400 text-sm">
              Connect your Last.fm account to get personalized music
              recommendations. Get an API key at{" "}
              <a
                href="https://www.last.fm/api/account/create"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                last.fm/api/account/create
              </a>
            </p>
            <Input
              label="Last.fm Username"
              placeholder="your-username"
              value={username}
              onValueChange={setUsername}
              startContent={
                <UserIcon className="text-foreground-400 h-4 w-4" />
              }
            />
            <Input
              label="API Key"
              placeholder="your-api-key"
              value={apiKey}
              onValueChange={setApiKey}
              startContent={<KeyIcon className="text-foreground-400 h-4 w-4" />}
              type="password"
            />
            <Button
              color="primary"
              onPress={handleConnect}
              isLoading={isConnecting}
              isDisabled={!username || !apiKey}
              className="w-fit"
            >
              Connect
            </Button>
          </CardBody>
        </Card>
      </>
    );
  }

  return (
    <>
      <h1 className="text-foreground mb-6 text-2xl font-bold">Discovery</h1>

      {/* Settings Card */}
      <Card className="mb-6">
        <CardBody className="gap-4 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <SparklesIcon className="text-primary h-6 w-6" />
              <div>
                <h2 className="text-lg font-semibold">Last.fm</h2>
                <p className="text-foreground-400 text-sm">
                  {settings.username}
                </p>
              </div>
            </div>
            <Button
              variant="flat"
              color="danger"
              size="sm"
              onPress={disconnect}
            >
              Disconnect
            </Button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Enable Discovery</p>
              <p className="text-foreground-400 text-xs">
                Periodically scan for new recommendations
              </p>
            </div>
            <Switch
              isSelected={settings.enabled}
              onValueChange={(v) => update({ ...settings, enabled: v })}
            />
          </div>

          {settings.enabled && (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Auto-download</p>
                  <p className="text-foreground-400 text-xs">
                    Automatically download high-confidence matches
                  </p>
                </div>
                <Switch
                  isSelected={settings.auto_download}
                  onValueChange={(v) =>
                    update({ ...settings, auto_download: v })
                  }
                />
              </div>

              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-sm font-medium">Confidence Threshold</p>
                  <p className="text-foreground-400 text-xs">
                    Minimum match confidence (0-100)
                  </p>
                </div>
                <Input
                  type="number"
                  value={String(settings.confidence_threshold)}
                  onValueChange={(v) => {
                    const n = parseInt(v, 10);
                    if (!Number.isNaN(n) && n >= 0 && n <= 100) {
                      update({ ...settings, confidence_threshold: n });
                    }
                  }}
                  min={0}
                  max={100}
                  className="w-20"
                  classNames={{ input: "font-mono text-center" }}
                />
              </div>
            </>
          )}
        </CardBody>
      </Card>

      {/* Stats + Actions */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardBody className="items-center py-4 text-center">
            <p className="text-foreground-400 text-xs">Pending</p>
            <p className="text-2xl font-bold">{stats?.pending ?? 0}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="items-center py-4 text-center">
            <p className="text-foreground-400 text-xs">Approved</p>
            <p className="text-2xl font-bold">{stats?.approved ?? 0}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="items-center py-4 text-center">
            <p className="text-foreground-400 text-xs">Rejected</p>
            <p className="text-2xl font-bold">{stats?.rejected ?? 0}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="items-center py-4 text-center">
            <p className="text-foreground-400 text-xs">Downloaded</p>
            <p className="text-2xl font-bold">{stats?.downloaded ?? 0}</p>
          </CardBody>
        </Card>
      </div>

      <div className="mb-6 flex gap-2">
        <Button
          color="primary"
          onPress={scan}
          isLoading={isScanning}
          startContent={!isScanning && <ScanIcon className="h-4 w-4" />}
        >
          Scan Now
        </Button>
        <Button
          variant="flat"
          color="secondary"
          onPress={generateSimilarTracks}
          isLoading={isGeneratingPlaylist}
          startContent={
            !isGeneratingPlaylist && <ListMusicIcon className="h-4 w-4" />
          }
        >
          Similar Tracks
        </Button>
        {pendingSuggestions.length > 0 && (
          <Button
            variant="flat"
            color="success"
            onPress={approveAll}
            startContent={<CircleCheckIcon className="h-4 w-4" />}
          >
            Approve All ({pendingSuggestions.length})
          </Button>
        )}
        <Button
          variant="flat"
          color="primary"
          onPress={createPlaylist}
          isLoading={isCreatingPlaylist}
          startContent={
            !isCreatingPlaylist && <ListPlusIcon className="h-4 w-4" />
          }
        >
          {pendingSuggestions.length > 0
            ? `Approve All & Create Discover Playlist`
            : `Rebuild Discover Playlist`}
        </Button>
        {suggestions.length > 0 && (
          <Button
            variant="flat"
            color="danger"
            onPress={clearAll}
            isLoading={isClearing}
            startContent={!isClearing && <Trash2Icon className="h-4 w-4" />}
            className="ml-auto"
          >
            Clear All
          </Button>
        )}
      </div>

      {/* Suggestions List */}
      {suggestions.length === 0 ? (
        <Card>
          <CardBody className="py-12 text-center">
            <SparklesIcon className="text-foreground-200 mx-auto mb-3 h-10 w-10" />
            <p className="text-foreground-400 text-sm">
              No suggestions yet. Run a scan to discover new music.
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {suggestions.map((s) => (
            <Card key={s.id}>
              <CardBody className="flex flex-row items-center gap-4 p-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{s.lastfm_track}</p>
                    {s.confidence >= 80 && (
                      <Chip
                        size="sm"
                        variant="flat"
                        color="success"
                        className="text-xs"
                      >
                        High
                      </Chip>
                    )}
                    {s.confidence >= 50 && s.confidence < 80 && (
                      <Chip
                        size="sm"
                        variant="flat"
                        color="warning"
                        className="text-xs"
                      >
                        Medium
                      </Chip>
                    )}
                    {s.confidence < 50 && s.confidence > 0 && (
                      <Chip
                        size="sm"
                        variant="flat"
                        color="danger"
                        className="text-xs"
                      >
                        Low
                      </Chip>
                    )}
                  </div>
                  <p className="text-foreground-400 text-sm">
                    {s.lastfm_artist}
                  </p>
                  {s.matched_title && (
                    <p className="text-foreground-400 mt-1 text-xs">
                      Match: {s.matched_title} — {s.matched_artist}{" "}
                      <span className="text-foreground-500">
                        ({Math.round(s.confidence)}%)
                      </span>
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {s.status === "pending" && (
                    <>
                      <Tooltip content="Approve & download">
                        <Button
                          isIconOnly
                          size="sm"
                          variant="flat"
                          color="success"
                          onPress={() => approve(s.id)}
                        >
                          <CircleCheckIcon className="h-4 w-4" />
                        </Button>
                      </Tooltip>
                      <Tooltip content="Reject">
                        <Button
                          isIconOnly
                          size="sm"
                          variant="flat"
                          color="danger"
                          onPress={() => reject(s.id)}
                        >
                          <CircleXIcon className="h-4 w-4" />
                        </Button>
                      </Tooltip>
                    </>
                  )}
                  {s.status === "approved" && (
                    <Chip size="sm" variant="flat" color="primary">
                      Downloading
                    </Chip>
                  )}
                  {s.status === "rejected" && (
                    <Chip size="sm" variant="flat" color="default">
                      Rejected
                    </Chip>
                  )}
                  {s.status === "downloaded" && (
                    <Chip size="sm" variant="flat" color="success">
                      Downloaded
                    </Chip>
                  )}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
