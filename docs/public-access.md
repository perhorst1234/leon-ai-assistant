# Publieke toegang en eerste registratie

De productie-VM draait Leon voor het lokale netwerk op `0.0.0.0:3000`, met de Python-backend op
`127.0.0.1:8765` en Ollama op `127.0.0.1:11434`. Caddy luistert op 8080/8443;
de Sagemcom-router koppelt publieke TCP-poorten 80/443 via UPnP aan die
poortnummers op de VM. DuckDNS wijst `leon-ai-assistant.duckdns.org` naar het
publieke IPv4-adres. Caddy beheert het Let's Encrypt-certificaat automatisch.
`leon-public-route.timer` vernieuwt elke 30 minuten de routerleases (60 minuten)
en het DuckDNS A-record. De privé DuckDNS-sleutel staat alleen in
`.runtime/duckdns-token`; geen sleutel staat in Git.

Open **https://leon-ai-assistant.duckdns.org**. Het eerste scherm vraagt om de
eenmalige instelcode uit `.runtime/leon-web-setup-code`. Kies vervolgens zelf een
wachtwoord van minimaal 12 tekens en bevestig het. Daarna is het account
geregistreerd en volstaat het wachtwoord. Er kan via de website geen tweede
account worden gemaakt. Het wachtwoord wordt met scrypt en een unieke salt in
`.runtime/leon-web-account.json` opgeslagen. De browser krijgt alleen een
HTTP-only, Secure, SameSite=Lax-sessiecookie; de backendtoken blijft op de
webserver. Uitloggen wist de browsercookie.

Voor direct gebruik op hetzelfde thuisnetwerk open je
**http://192.168.178.177:3000** (actueel op 25 september 2026). Daar gebruikt de sessiecookie vanwege lokaal
HTTP geen `Secure`-attribuut, maar blijft hij HTTP-only en SameSite=Lax. De
Python-backend, database en Ollama blijven uitsluitend op loopback bereikbaar.
Het adres komt via DHCP; controleer na een VM-/routerwissel met `hostname -I` en
gebruik het actuele `192.168.178.x`-adres met poort 3000.

De router lijkt geen NAT-loopback toe te laten: een aanvraag vanuit de VM naar
het eigen publieke IPv4-adres loopt vast. Externe meetpunten bereikten HTTPS
wel (2 van 3 HTTP-controles, 3 van 3 TCP-controles op 21 september 2026). Bij
een soortgelijk probleem op het eigen wifi-netwerk kan tijdelijk de door
`leon-temporary-tunnel.service` gemaakte `trycloudflare.com`-link worden
gebruikt. Lees de actuele URL uit `.runtime/leon-temp-origin` of het
servicejournaal. Die gratis Quick Tunnel heeft geen uptimegarantie en verandert
na een tunnelherstart; de wrapper werkt de private origin-file dan automatisch
bij. De vaste DuckDNS-link is de primaire publieke route.

Controleer de diensten met:

```sh
systemctl --user status leon-web leon-caddy leon-public-route.timer leon-temporary-tunnel
curl -fsS http://127.0.0.1:3000/api/auth
```

Het publieke adres en de certificaatuitgifte zijn op 21 september 2026 van
buitenaf geverifieerd. Registratie, fout wachtwoord, login, sessiecookie,
afgeschermde API en logout zijn tegen een geïsoleerde webinstantie getest;
het echte productieaccount is nog leeg, zodat de eigenaar het wachtwoord zelf
kan kiezen. De tijdelijke link is alleen een fallback en geen onderdeel van
de permanente beschikbaarheidsgarantie.
