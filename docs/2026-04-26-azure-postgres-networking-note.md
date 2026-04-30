# Azure PostgreSQL Networking Note for NL-SQL

Date: 2026-04-26

## Why the error happens

The current standalone NL-SQL route opens PostgreSQL from the local machine through [src/nlsql/db.py](/E:/DatasenseProject/CapstoneprojectDatasense/src/nlsql/db.py:68).

The connection flow is:

1. `_preflight_postgres_socket(settings)` in [src/nlsql/db.py](/E:/DatasenseProject/CapstoneprojectDatasense/src/nlsql/db.py:68)
2. raw TCP connect to `pg_host:pg_port`
3. only after TCP works, token/password authentication starts

So this error:

```text
RuntimeError: Network path to PostgreSQL is not reachable. Target=capstone1.postgres.database.azure.com:5432
```

is a **network reachability problem before authentication**.

It is not an OpenAI issue.
It is not an NL-SQL SQL-generation issue.
It is not primarily an Azure login issue.

## Why it worked yesterday and fails today

The current development path depends on direct public access from the laptop to Azure Database for PostgreSQL.

That means the working path is:

```text
Laptop -> public internet -> Azure PostgreSQL public endpoint:5432
```

This is fragile because the laptop's public IP can change due to:

- home ISP reassignment
- router reconnect
- hotspot change
- mobile network NAT changes
- VPN on/off
- office or hostel network switching

If the server is configured with **Public access (allowed IP addresses)** and the public IP changes, the firewall rule becomes stale and the TCP path stops working.

## Temporary development fix

For local development, the fix is:

1. check current public IP
2. update Azure PostgreSQL firewall rules
3. wait a few minutes
4. rerun the CLI

Useful checks:

```powershell
Test-NetConnection capstone1.postgres.database.azure.com -Port 5432
(Invoke-RestMethod 'https://api.ipify.org?format=json').ip
```

If `TcpTestSucceeded` is `False`, the route will fail before SQL generation starts.

## Enterprise-grade fix

Do not rely on the end user's IP or the developer laptop for database access.

Correct architecture:

```text
Frontend
  -> HTTPS
Backend API / NL-SQL service
  -> controlled Azure network path
Azure PostgreSQL
```

Users should never connect to PostgreSQL directly.
The browser should call only the backend over HTTPS.

### Recommended production target

1. deploy the NL-SQL backend in Azure
2. connect backend and PostgreSQL over **private access / VNet**
3. authenticate backend with managed identity or Entra-based auth
4. keep PostgreSQL unreachable from arbitrary client IPs

This removes dependence on changing laptop IPs.

### If private access cannot be used immediately

Use a stable backend egress IP:

```text
Frontend
  -> Azure backend
  -> NAT Gateway static public IP
  -> Azure PostgreSQL firewall allowlists only that static IP
```

This is still better than allowing developer or user IPs.

## Why this matters for the current code

The NL-SQL route itself is fine:

- classification
- prompt building
- SQL generation
- validation
- execution
- answer rendering

But none of it runs if TCP `5432` fails first.

So the production fix is a **network architecture change**, not a prompt or SQL change.

## Immediate recommendation for this project

Short term:

- keep using public access only for local development
- update the firewall rule when the client public IP changes

Project/demo deployment:

- deploy backend in Azure
- move PostgreSQL connectivity out of the laptop path
- prefer VNet/private access

## Verified NL-SQL terminal output shape

When TCP and database access work, the improved CLI prints answer-first text like this:

```text
Question
Which states had the highest total property damage?

Answer
Texas had the highest total property damage in the loaded NOAA storm events, followed by Florida.

How It Was Computed
Executed a read-only PostgreSQL query over NOAA storm events, aggregated and ranked the matching records, returned 2 rows, and summarized the validated results.

Evidence
1. Texas | $1,200,000
2. Florida | $950,000
```

And for trade:

```text
Question
Which countries had the highest export value in 2023?

Answer
China had the highest export value in the loaded Comtrade rows, with the United States next.

How It Was Computed
Executed a read-only PostgreSQL query over UN Comtrade trade flows, aggregated and ranked the matching records, returned 2 rows, and summarized the validated results.

Evidence
1. China | $8,400,000
2. United States | $7,950,000
```

Debug mode still shows raw internals:

```powershell
.\.venv\Scripts\python.exe .\run_nlsql_query.py --question "Which companies appear in both FDA warning letters and the OFAC SDN list?" --tenant-id capstone --debug
```

## Azure references

These Azure docs support the production recommendation:

- Firewall rules and public access for Azure Database for PostgreSQL Flexible Server:
  https://learn.microsoft.com/azure/postgresql/flexible-server/concepts-firewall-rules
- Public networking / access modes:
  https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-networking-public
- Disabling public access:
  https://learn.microsoft.com/en-us/azure/postgresql/network/how-to-networking-servers-deployed-public-access-disable-public-access
- App Service outbound IP behavior:
  https://learn.microsoft.com/en-us/azure/app-service/ip-address-change-outbound
- NAT Gateway with App Service:
  https://learn.microsoft.com/en-us/azure/app-service/overview-nat-gateway-integration
