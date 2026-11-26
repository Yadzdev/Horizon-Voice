# API reference — current endpoints

All endpoints are prefixed with `/api/v1`. JSON request/response bodies are used unless noted. BDS-only operations authenticate with `X-Server-Key`; owner operations use `Authorization: Bearer <access_token>`; player browser sessions use the HttpOnly `hv_session` cookie.

## Health and owner authentication

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | Public | Liveness response |
| POST | `/auth/register` | Public | Create owner account; password minimum 12 chars |
| POST | `/auth/login` | Public | Issue short-lived owner JWT |
| GET | `/auth/me` | Owner | Current account |

## Server registration and activation

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/servers` | Owner | Create pending tenant and 15-minute activation code |
| POST | `/registration/activate` | Public one-time code | Activate BDS; returns server key once |

## Public server portal and cover image

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/public/servers/{slug}` | Public | Return safe public server details and optional cover URL for the player portal |
| GET | `/public/servers/{slug}/image` | Public | Serve the optimized WebP cover for an active server |
| PUT | `/dashboard/servers/{server_id}/image` | Owner | Upload/replace an owned server cover as raw PNG, JPEG or WebP body (2.5 MB maximum); API validates and normalizes to WebP |

## Browser pairing and player state

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/pairing/codes` | Tenant host / `X-Tenant-Slug` | Create a short-lived browser session and six-digit pairing code; sets HttpOnly cookie |
| POST | `/pairing/claim` | BDS server key | Claim pairing code and bind BDS session identity |
| GET | `/pairing/status` | Browser cookie | Return whether this browser session is paired |
| POST | `/pairing/revoke` | Browser cookie | Revoke current browser session |
| POST | `/players/positions` | BDS server key | Batch player position and dimension updates; expires stale presence and schedules LiveKit reconciliation |
| POST | `/players/leave` | BDS server key | Immediately expire a BDS entity, remove group membership and disconnect its LiveKit participant |
| GET | `/players/groups?identity_key=...` | BDS server key | List public groups and the player’s own active private group |
| POST | `/players/groups/create` | BDS server key | Create and automatically join a public/private group from a BDS form |
| POST | `/players/groups/join` | BDS server key | Join a group from its invitation code; private groups require the password |
| POST | `/players/groups/leave` | BDS server key | Leave the active group and resume proximity mode |
| POST | `/players/self-mute` | BDS server key | Set a player's self-mute state |
| GET | `/players/voice-states` | BDS server key | Return online voice indicator states |

## Voice / groups

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/voice/token` | Browser cookie | Issues a short-lived LiveKit token with publishing controls; browser-side auto-subscription is disabled and subscriptions are granted by the API only after authorization |
| POST | `/voice/self-mute` | Browser cookie | Persist self-mute and revoke/restore media publishing |
| POST | `/voice/deafen` | Browser cookie | Stop receiving remote subscriptions |
| POST | `/voice/local-mute/{target_player_id}` | Browser cookie | Locally mute one player for this listener only |
| POST | `/voice/speaking` | Browser cookie | Update the speaking presentation indicator |
| POST | `/voice/refresh` | Browser cookie | Schedule server-side subscription reconciliation |
| GET | `/voice/nearby` | Browser cookie | Return players, distance and server-authorized eligibility for the current listener |
| POST | `/voice/moderation/{player_id}/mute` | Owner | Persist owner moderation mute, revoke/restore the LiveKit publisher permission, and reconcile authorized listeners |
| POST | `/groups` | Browser cookie | Create group record and join-code; optional Argon2 password |
| POST | `/groups/join` | Browser cookie | Join a same-tenant group after password and capacity checks |
| POST | `/groups/leave` | Browser cookie | Leave all current groups and return to proximity mode |
| DELETE | `/groups/{group_id}` | Browser cookie / group owner | Delete own group and return every member to proximity mode |

## Owner dashboard

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/dashboard/servers` | Owner | List owned tenants, including public cover URL when configured |
| GET | `/dashboard/servers/{server_id}` | Owner | Server metrics |
| PATCH | `/dashboard/servers/{server_id}/settings` | Owner | Update max distance and voice-enabled flag |

## WebSocket

`/api/v1/voice/events` authenticates using the browser `hv_session` cookie and currently broadcasts process-local tenant events. It is not a distributed WebSocket bus; use one API worker until Redis pub/sub is implemented.

## Known gaps

Password reset and email verification are not implemented. The speaking indicator currently reflects the browser/LiveKit active-speaker signal and is presentation-only; the API never uses it to authorize audio. Rate limits, WebSocket fanout, and media synchronization caches are process-local, so the provided production Compose starts a single API worker and must not be horizontally scaled. BDS identity uses `Player.id` and is session-scoped, not a persistent XUID; a player must pair again after leaving and rejoining if BDS assigns a new entity ID. The current LiveKit SDK calls, webhook contract, TURN path, and add-on must be tested against the exact deployed server and network versions before production use. The API token endpoint returns 503 when LiveKit is not configured.
