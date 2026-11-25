import {
  world, system, CustomCommandPermissionLevel, CustomCommandParamType,
  CustomCommandStatus
} from "@minecraft/server";
import { HttpRequestMethod } from "@minecraft/server-net";
import { getServerSecret, apiRequest } from "./network.js";
import { activateServer, showVoiceMenu, showGroupMenu, showHelp, toggleServerMute } from "./forms.js";
import { updateVoiceNameTags } from "./name-tags.js";

const POSITION_INTERVAL_TICKS = 20; // 1 second; batched and movement-throttled.
const STATE_INTERVAL_TICKS = 20;
const MIN_MOVE_DISTANCE = 0.5;
let lastPositionSnapshot = new Map();
let lastStatePoll = 0;
let stateCache = [];
let inFlight = false;
let lastPresenceHeartbeat = 0;
let nextPositionRetryTick = 0;
let positionRetryDelayTicks = POSITION_INTERVAL_TICKS;

function commandResult(message, success = true) {
  return { status: success ? CustomCommandStatus.Success : CustomCommandStatus.Failure, message };
}

function registerCommands(event) {
  const registry = event.customCommandRegistry;
  registry.registerCommand({
    name: "horizon:voz",
    description: "Abre o menu do Horizon Voice",
    permissionLevel: CustomCommandPermissionLevel.Any,
    optionalParameters: [
      { type: CustomCommandParamType.String, name: "action" }
    ]
  }, (origin, args) => {
    const player = origin.sourceEntity;
    if (!player || player.typeId !== "minecraft:player") return commandResult("Este comando precisa ser executado por um jogador.", false);
    const action = String(args?.[0] ?? "menu").toLowerCase();
    system.run(() => {
      if (action === "mute") void toggleServerMute(world, player, true);
      else if (action === "unmute") void toggleServerMute(world, player, false);
      else if (action === "grupos") void showGroupMenu(world, player);
      else if (action === "ajuda") showHelp(player);
      else showVoiceMenu(world, player);
    });
    return commandResult("Horizon Voice: abrindo menu...");
  });

  registry.registerCommand({
    name: "horizon:cadastrarvoice",
    description: "Ativa este BDS no Horizon Voice",
    permissionLevel: CustomCommandPermissionLevel.Admin,
    mandatoryParameters: [{ type: CustomCommandParamType.String, name: "activation_code" }]
  }, (origin, args) => {
    const code = String(args?.[0] ?? "").trim();
    if (!code) return commandResult("Informe o código de ativação.", false);
    const player = origin.sourceEntity;
    system.run(() => void activateServer(world, player, code));
    return commandResult("Horizon Voice: validando código de ativação...");
  });
}

system.beforeEvents.startup.subscribe(registerCommands);

async function sendPositions() {
  const secret = getServerSecret(world);
  if (!secret || inFlight || system.currentTick < nextPositionRetryTick) return;
  const players = world.getAllPlayers();
  const changed = [];
  for (const player of players) {
    const loc = player.location;
    const dim = player.dimension.id;
    const previous = lastPositionSnapshot.get(player.id);
    const moved = !previous || previous.dimension !== dim ||
      Math.hypot(loc.x - previous.x, loc.y - previous.y, loc.z - previous.z) >= MIN_MOVE_DISTANCE;
    if (moved || !previous || system.currentTick - previous.tick >= POSITION_INTERVAL_TICKS * 4) {
      changed.push({
        identity_key: player.id,
        display_name: player.name,
        dimension: dim,
        x: loc.x,
        y: loc.y,
        z: loc.z
      });
      lastPositionSnapshot.set(player.id, { x: loc.x, y: loc.y, z: loc.z, dimension: dim, tick: system.currentTick });
    }
  }
  // An empty batch is sent as a 20-second heartbeat so the API can expire players
  // after the last player leaves the server.
  if (!changed.length && system.currentTick - lastPresenceHeartbeat < POSITION_INTERVAL_TICKS * 4) return;
  inFlight = true;
  lastPresenceHeartbeat = system.currentTick;
  try {
    for (let offset = 0; offset < changed.length; offset += 200) {
      const batch = changed.slice(offset, offset + 200);
      await apiRequest("/players/positions", { serverSecret: secret, body: { players: batch } });
    }
    if (changed.length === 0) {
      await apiRequest("/players/positions", { serverSecret: secret, body: { players: [] } });
    }
    positionRetryDelayTicks = POSITION_INTERVAL_TICKS;
    nextPositionRetryTick = 0;
  } catch (error) {
    for (const item of changed) lastPositionSnapshot.delete(item.identity_key);
    nextPositionRetryTick = system.currentTick + positionRetryDelayTicks;
    positionRetryDelayTicks = Math.min(positionRetryDelayTicks * 2, 6000);
  } finally {
    inFlight = false;
  }
}

async function refreshVoiceStates() {
  const secret = getServerSecret(world);
  if (!secret) return;
  try {
    const response = await apiRequest("/players/voice-states", { method: HttpRequestMethod.Get, serverSecret: secret });
    stateCache = Array.isArray(response.players) ? response.players : [];
    updateVoiceNameTags(world.getAllPlayers(), stateCache);
  } catch {
    // Keep the last known pairing labels; the next poll attempts recovery.
  }
}

system.runInterval(() => { void sendPositions(); }, POSITION_INTERVAL_TICKS);
system.runInterval(() => {
  if (system.currentTick - lastStatePoll >= STATE_INTERVAL_TICKS) {
    lastStatePoll = system.currentTick;
    void refreshVoiceStates();
  }
}, 20);

world.afterEvents.playerLeave.subscribe(event => {
  lastPositionSnapshot.delete(event.playerId);
  const secret = getServerSecret(world);
  if (secret) {
    void apiRequest("/players/leave", {
      serverSecret: secret,
      body: { identity_key: event.playerId }
    }).catch(() => {
      // The API also expires stale players after 45 seconds if this callback
      // cannot reach the network. Never block BDS shutdown/gameplay.
    });
  }
});
