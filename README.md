# GRAVIA

Website der Junior Company der HTL Hollabrunn. Python 3.10+ genügt; keine zusätzlichen Pakete nötig.

## Lokal starten

```sh
python3 server.py
```

Öffne http://localhost:8000. Im gleichen Netzwerk funktioniert die lokale IP des Computers mit Port 8000. Der bisherige `python3 -m http.server` kann keine Anfragen verarbeiten und darf nach Einrichtung der Zugangsdaten nicht verwendet werden, da er private Projektdateien ausliefern könnte.

## Anfragen per E-Mail aufs Handy

1. Richte ein Versandpostfach mit SMTP-Zugang ein. Nutze ein separates App-Passwort, falls der Anbieter dies unterstützt.
2. Kopiere `.env.example` nach `.env` und trage SMTP-Server, Port, Benutzer, Passwort, Absender und Empfänger ein. Werte mit Leerzeichen oder Sonderzeichen müssen für die Shell in einfache Anführungszeichen gesetzt werden. `.env` ist eine lokale Shell-Datei und wird nicht automatisch geladen.
3. Starte in bash/zsh:

```sh
set -a
source .env
set +a
python3 server.py
```

4. Aktiviere Benachrichtigungen für das Empfängerpostfach in deiner Handy-Mail-App. Prüfe auch den Spamordner.
5. Sende eine echte Testanfrage und prüfe den Eingang am Handy. Über „Antworten“ antwortest du direkt an die anfragende Person.

SMTP verwendet TLS: Port 465 direkt, andere Ports (typisch 587) mit STARTTLS. Zugangsdaten bleiben auf dem Server. Ohne vollständige Konfiguration meldet das Formular, dass der Versand noch eingerichtet wird. Vollständige Variablen allein bestätigen noch keine funktionierende Anmeldung oder Zustellung.

## Speicherung und Versand

Anfragen werden vor der Eingangsbestätigung in `data/inquiries.sqlite3` gespeichert. Ein Hintergrundprozess verschickt die Benachrichtigung und wiederholt fehlgeschlagene Versuche mit wachsendem Abstand (maximal eine Stunde). Neustarts erhalten die Warteschlange. Der Server muss laufen, damit Nachrichten versendet werden. „Gespeichert“ bestätigt den Eingang auf dem Server, nicht die Zustellung am Handy.

Der Browser verwendet pro Anfrage eine ID, sodass ein erneuter Versuch nach einem Verbindungsfehler dieselbe Anfrage nicht nochmals speichert. In seltenen Fällen kann eine Mail doppelt eintreffen, etwa wenn der Mailserver die Nachricht angenommen hat, die Verbindung jedoch vor seiner Bestätigung abbricht. Die Anfragenummer hilft beim Zuordnen.

Serverseitige Längen- und Eingabeprüfung, ein verstecktes Spamfeld und maximal fünf neue Anfragen je IP pro Stunde bieten einen Basisschutz. Öffentliches Hosting braucht zusätzlich HTTPS, einen dauerhaft laufenden Python-Prozess und dauerhaften Speicher. Bei Reverse-Proxys zählt aktuell die Proxy-IP; vor öffentlichem Betrieb ist ein zum Hosting passendes Rate-Limit nötig. Es gibt kein öffentliches Verwaltungsinterface. Fehlermeldungen im Terminal enthalten keine Anfragetexte oder Zugangsdaten.

Status prüfen (lokal):

```sh
python3 -c "import sqlite3; db=sqlite3.connect('data/inquiries.sqlite3'); print(db.execute('select state, count(*) from inquiries group by state').fetchall())"
```

`pending`: noch zu versenden; `sent`: vom SMTP-Server angenommen. Datenbank geschützt sichern und erledigte Anfragen nach einer festgelegten Aufbewahrungsfrist löschen. Vor Veröffentlichung echte Kontaktdaten, Impressum und Datenschutzhinweise einschließlich E-Mail-Dienst ergänzen. Es ist noch kein Hosting eingerichtet.

## Prüfen

```sh
python3 -m unittest -v test_server.py
node --check script.js
```

Die automatischen Tests verwenden eine temporäre Datenbank und einen simulierten Versand; sie senden keine E-Mails.
