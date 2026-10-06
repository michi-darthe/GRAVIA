# GRAVIA

Website der Junior Company der HTL Hollabrunn. Python 3.10+ genügt; keine zusätzlichen Pakete nötig.

## Lokal starten

```sh
python3 server.py
```

Öffne http://localhost:8000. Im gleichen Netzwerk funktioniert die lokale IP des Computers mit Port 8000. Der bisherige `python3 -m http.server` kann keine Anfragen verarbeiten und darf nach Einrichtung der Zugangsdaten nicht verwendet werden, da er private Projektdateien ausliefern könnte.

## Anfragen per E-Mail aufs Handy

Empfänger für neue Anfragen ist `gravia.at@outlook.com` (`MAIL_TO`). Nach Änderungen an `.env` den Python-Server neu starten. Falls das Hosting `MAIL_TO` als Umgebungsvariable setzt, muss die Adresse auch dort aktualisiert werden, da diese Einstellung Vorrang hat.

1. Richte ein Versandpostfach mit SMTP-Zugang ein. Nutze ein separates App-Passwort, falls der Anbieter dies unterstützt.
2. Kopiere `.env.example` nach `.env` und trage SMTP-Server, Port, Benutzer, Passwort, Absender und Empfänger ein. Werte mit Leerzeichen oder Sonderzeichen müssen für die Shell in einfache Anführungszeichen gesetzt werden. Der Start mit `python3 server.py` lädt einfache KEY=value-Einträge aus `.env` automatisch; bereits gesetzte Umgebungsvariablen haben Vorrang.
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

## Kundenkonten und Warenkorb

Über **Mein Konto** lassen sich Konten erstellen (Passwort mindestens 12 Zeichen), anmelden und abmelden. Auf Produkt- und Designstudioseiten übernimmt **In den Warenkorb** die aktuelle Gestaltung einschließlich Variante, Symbolen und Positionen. Ist eine Anmeldung nötig, wird das gewählte Produkt im selben Browser-Tab bis zur Anmeldung zwischengespeichert und anschließend hinzugefügt. Der Warenkorb ist kontogebunden, in SQLite gespeichert und unterstützt Mengenänderungen und das Entfernen einzelner Positionen. Verschiedene Gestaltungen bleiben getrennte Positionen.

Nach dem Update den Python-Server neu starten. Die zusätzlichen Tabellen werden automatisch in der bestehenden Datenbank angelegt; bestehende Anfragen bleiben erhalten. Kein zusätzlicher Datenbankdienst und keine neuen Python-Pakete erforderlich.

Passwörter werden mit individuellem Salt und scrypt gehasht. Sitzungen laufen nach sieben Tagen ab; der Browser erhält ein HttpOnly-/SameSite-Cookie, die Datenbank speichert nur dessen Hash. Anmeldung und Registrierung sind auf zusammen 15 Versuche je IP innerhalb von 15 Minuten begrenzt. Beim Betrieb hinter einem Proxy gilt dieselbe Einschränkung bezüglich der Proxy-IP wie für Anfragen.

**Für öffentliches HTTPS-Hosting `GRAVIA_COOKIE_SECURE=1` setzen**, damit das Sitzungscookie ausschließlich über HTTPS übertragen wird. Lokal unter HTTP bleibt die Variable auf `0`. Konten und Warenkörbe liegen in derselben geschützten Datenbank wie die Anfragen und müssen entsprechend gesichert werden.

Diese erste Version speichert Produkte mit „Preis auf Anfrage“. Sie enthält keinen Bestellabschluss, keine Bezahlung, keine E-Mail-Verifizierung und keine Passwort-Wiederherstellung. Angebote werden weiterhin über das bestehende Produkt-Anfrageformular eingeholt.

Prüfen:

```sh
python3 -m unittest -v test_server test_shop
node --check shop.js
node --check script.js
node --check produkt.js
```


## Supabase-Anmeldung

Sind `SUPABASE_URL` und `SUPABASE_PUBLISHABLE_KEY` in `.env` gesetzt, verwenden Registrierung und Anmeldung Supabase Auth. Server neu starten: `python3 server.py`. In Supabase unter Authentication → URL Configuration für lokale Tests Site URL `http://localhost:8000` und Redirect URL `http://localhost:8000/**` eintragen.

Bei aktivierter E-Mail-Bestätigung zuerst den Link in der E-Mail öffnen und anschließend über `konto.html` anmelden. Die Rückleitung allein meldet nicht an. Passwörter werden in diesem Modus nur zur Authentifizierung an Supabase übermittelt und nicht lokal gespeichert. Der Server erzeugt nach erfolgreicher Anmeldung eine eigene siebentägige HttpOnly-Sitzung; Supabase-Tokens werden nicht gespeichert. Abmelden beendet diese lokale Sitzung. Eine Sperrung oder Passwortänderung in Supabase widerruft bestehende lokale Sitzungen nicht automatisch; diese müssen bei Bedarf zusätzlich aus der lokalen Tabelle `sessions` entfernt werden.

Warenkörbe, Sitzungen und Anfragen bleiben in SQLite. Supabase-Profile werden separat anhand ihrer Nutzer-ID gespeichert. Bestehende lokale Konten und Warenkörbe bleiben erhalten, werden jedoch nicht automatisch zu Supabase übertragen oder anhand einer E-Mail-Adresse verknüpft. Für Supabase neu registrieren. Ohne Supabase-Konfiguration gilt weiterhin die oben beschriebene lokale Anmeldung; bei unvollständiger Konfiguration oder einem Supabase-Ausfall gibt es keinen Rückfall auf lokale Passwörter.

Tests: `python3 -m unittest -v test_server test_shop test_supabase`. Die Supabase-Tests simulieren den Anbieter und versenden keine Bestätigungs-E-Mails.

## SVG-Designstudio und Verwaltung

`gestalten.html` ist jetzt ein eigenständiger SVG-Editor mit mehreren Texten, Rechtecken, Ellipsen, PNG/JPEG-Fotos, Freihandlinien, Objekt-Reihenfolge, Duplizieren, Rückgängig/Wiederholen und SVG-Download. Gestaltung und Anfrage werden direkt aus dem Studio versendet; der bisherige textbasierte Warenkorb bleibt separat. Es werden keine STL-Dateien erzeugt.

`svg_products.json` enthält Produktmaße in Millimetern und den Gravurbereich `[x, y, breite, höhe]`. Die mitgelieferten Werte für Brett und rechteckigen Anhänger sind **Beispielmaße**, keine bestätigten Produktionsmaße. Tatsächliche Maße eintragen und erst danach `confirmed` auf `true` setzen. Andere Anhängerformen und 3D-Produkte sind noch nicht als SVG-Produkte eingerichtet. Die SVG-Zeichenfläche entspricht der Produktgröße; Inhalte außerhalb des Gravurbereichs werden abgeschnitten. Produktfläche, Auswahlrahmen und Hilfslinien werden nicht exportiert.

Die Speicherung erfolgt atomar in `inquiries` und `inquiry_designs` der bestehenden SQLite-Datei. SVG, validierte Objektbeschreibung, Produktdaten zum Anfragezeitpunkt, Menge und Bearbeitungsstatus bleiben erhalten. SVG-Anfragen werden auch ohne SMTP-Konfiguration gespeichert; die bestehende Versandwarteschlange versendet Benachrichtigungen, sobald SMTP eingerichtet ist. Supabase übernimmt weiterhin nur die Authentifizierung. Diese Daten erscheinen daher nicht im Supabase Table Editor.

### Admin einrichten

1. Mit dem gewünschten Konto anmelden.
2. Dessen Nutzer-ID unter Supabase Authentication → Users ablesen. Im lokalen Auth-Modus steht die ID in `customers`.
3. In `.env` `GRAVIA_ADMIN_IDS=nutzer-id` setzen; mehrere IDs mit Komma trennen.
4. Python-Server neu starten und `http://localhost:8000/admin.html` öffnen.

Die Admin-API prüft das Sitzungscookie und die freigeschaltete ID bei jeder Anfrage. Ohne Freischaltung erhält niemand Zugriff. Die Verwaltung zeigt die neuesten 200 SVG-Anfragen und bietet Dateidownload sowie die Statuswerte Neu / In Prüfung / In Produktion / Erledigt. Kundendaten werden nicht auf der öffentlichen Admin-HTML-Seite eingebettet.

### Dateiformate und Grenzen

- Fotos: PNG/JPEG bis 2 MB je Foto, gesamte Anfrage maximal 6 MB; eingebettet in SVG, keine automatische Vektorisierung.
- SVG-Import: bis 500 KB, benötigt `viewBox`; statische Geometrie, Texte, Gruppen, Verläufe und Clipping. Skripte, externe Ressourcen, Animationen, Filter, eingebettete Fotos und nicht unterstützte Stile werden zurückgewiesen. Inkscape-Dateien ggf. als einfache SVG exportieren und komplexe Effekte zuvor in Pfade umwandeln. Importierte SVG wird als gemeinsames Objekt bewegt und skaliert, nicht knotenweise editiert.
- Vier generische Schriftfamilien; deren konkrete Darstellung hängt vom System ab. Keine mitgelieferten Schriftdateien und keine automatische Umwandlung von Text in Pfade. Vor Produktion auf dem Zielrechner prüfen und in Inkscape in Pfade umwandeln.
- Bis zu 80 Objekte; 30 Undo-Schritte im Arbeitsspeicher. Kein automatisches Speichern oder Wiederöffnen eines bearbeitbaren Entwurfs; beim Neuladen gehen ungesendete Änderungen verloren.
- Der Editor ist kein vollständiger Inkscape-Ersatz: keine booleschen Pfadoperationen, Knotenbearbeitung, Mehrfachauswahl/Gruppierung, Filter oder Erweiterungen. Lasereinstellungen und Materialprüfung erfolgen in der Produktionssoftware.

Prüfung: `python3 -m unittest -v test_server test_shop test_supabase test_svg` und `node --check gestalten.js`, `node --check admin.js`. Die Tests verwenden isolierte Datenbanken und senden keine echten E-Mails.

## Automatische SVG als E-Mail-Anhang

Der Kundenablauf verwendet wieder die einfache Produktbearbeitung in `produkt.html`. Der Einstieg „Professionell bearbeiten“ wurde entfernt. Beim Absenden sendet der Browser die strukturierten Gestaltungsdaten mit; der Server erzeugt und speichert die SVG automatisch. Die vorhandene SMTP-Warteschlange hängt die gespeicherte Datei als `image/svg+xml` an die E-Mail an `MAIL_TO` an. Wiederholungsversuche verwenden dieselbe gespeicherte Datei. Der Kunde muss weder eine Datei exportieren noch hochladen.

Text, zweite Zeile, Schriftstil, Größe, Ausrichtung und Position fließen in die SVG ein. Produktvariante, Kette und Menge bleiben in den Anfragedaten erhalten. Für Produkte ohne hinterlegte Maße wird eine ausdrücklich als Entwurf gekennzeichnete 100 × 100 mm Zeichenfläche verwendet; auch die Anhängerformen benötigen noch bestätigte Produktionsvorlagen. Vor Fertigung Maße und Schrift prüfen. Vorhandene SVG-Anfragen aus dem erweiterten Editor erhalten ebenfalls den Dateianhang.

Für den tatsächlichen Postfacheingang müssen SMTP und `MAIL_TO` eingerichtet sein und der Python-Server laufen. „Gespeichert“ bestätigt weiterhin den Eingang auf dem Server, nicht die E-Mail-Zustellung.

## Holzsortiment

Vier Modelle: Compact (22 × 15 × 1,5 cm, 7,90 €), Classic (28 × 22 × 1,5 cm, 10,90 €), Grand (33 × 22 × 1,5 cm, 12,90 €), Serving (58 × 19 × 1,5 cm, 14,90 €). Verkaufspreise inkl. 20 % USt. mit individueller Gravur. `boards.js` enthält die öffentlichen Beschreibungen und Preise; `svg_products.json` die Maße in Millimetern und SVG-Vorlagen. Änderungen an beiden Katalogen abgleichen. Die bisherige ID `wood` bleibt für gespeicherte Warenkörbe und Designs erhalten.

Die Fotos sind als Beispielbilder gekennzeichnet. Die Gravurfläche hat vorläufig 10 mm Rand; Position und nutzbare Fläche müssen vor Fertigung am jeweiligen Brett geprüft werden.

## Brett-Sets

`sets.html` bietet Kitchen Set (28,90 €), Complete Set (41,90 €) und eigene Kombinationen. Jede der vier Brett-IDs kann einmal gewählt werden. Zu jedem ausgewählten Brett ist ein eigener Gravurtext mit 1–28 Zeichen erforderlich; die Gravur ist enthalten. Mehrere identische Sets werden über die Set-Anzahl bestellt bzw. angefragt. Alle Preise enthalten 20 % USt.

`set_catalog.json` definiert die fertigen Kombinationen und die Rabattstaffel. `sets-core.js` berechnet die sofortige Vorschau; `board_sets.py` validiert die IDs und Gravuren und berechnet den verbindlichen Warenkorb-/Anfragepreis erneut. Reihenfolge und vom Browser übermittelte Preise haben keinen Einfluss: Kitchen und Complete haben stets Vorrang vor dem individuellen Rabatt. Geldbeträge werden in Cent berechnet.

Warenkorbpositionen speichern die Brett-IDs und Gravuren strukturiert in der bestehenden Datenbank. Vorhandene Positionen bleiben erhalten; keine zusätzliche Datenbankmigration erforderlich. Die Anmeldung übernimmt auch vorgemerkte Sets. Set-Anfragen laufen über die bestehende Versandwarteschlange und enthalten Preisaufstellung, Gravurtexte und je Brett eine SVG-Datei. Sie werden in `inquiries.payload` gespeichert; die bisherige SVG-Adminansicht listet weiterhin einzelne SVG-Anfragen.

Nach Änderungen den Python-Server neu starten. Für die Veröffentlichung auch `board_sets.py`, `set_catalog.json`, `sets.html`, `sets.css`, `sets.js` und `sets-core.js` mitnehmen.

Prüfen:

```sh
python3 -m unittest -v test_server.py test_shop.py test_svg.py test_supabase.py test_sets.py
node test_sets_core.cjs
```

Die Set-Tests prüfen alle 15 Kombinationen in jeder Auswahlreihenfolge, Pflichtgravuren, manipulierte Preise, Warenkorbzugriff, Speicherung und SVG-E-Mail-Anhänge mit simuliertem Versand.
