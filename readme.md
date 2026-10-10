# ChrząszczBOT

Bot Discord publikujący codziennie o 18:00 (czas `Europe/Warsaw`) 10 pierwszych
ofert z rankingu [Pepper Najgorętsze](https://www.pepper.pl/najgoretsze), razem
z ceną, temperaturą, linkiem i zdjęciem każdej okazji.

Opis architektury, wdrożeń, kluczy SSH i codziennej obsługi:
[PROJEKT.md](PROJEKT.md).

## Uruchomienie

1. Zainstaluj Python 3.10 lub nowszy i zależności:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

2. Ustaw token bota w zmiennej `DISCORD_TOKEN` albo umieść go w lokalnym pliku
   `token.txt` (plik jest ignorowany przez Git).

3. Uruchom:

   ```bash
   python3 main.py
   ```

Domyślnie bot publikuje na pierwszym znalezionym kanale tekstowym `promocje`.
Można to zmienić zmienną `DISCORD_CHANNEL` lub, dokładniej, ustawić
`DISCORD_CHANNEL_ID` na numeryczne ID kanału.

Komenda `/promocje` publikuje ranking od razu i służy do ręcznego testowania.
Komenda `/darmowegry` pokazuje gry aktualnie do odebrania w dwóch sekcjach:
- **Epic Games Store** — promocje dla Polski, bez subskrypcji.
- **Amazon Prime** — pełne gry wymagające aktywnej subskrypcji Prime,
  z linkiem do odbioru w Amazon Luna i terminem zakończenia oferty.

Bot pobiera dane bezpośrednio z katalogów Epic i Amazon. Pomija zapowiedzi,
wygasłe oferty oraz dodatki; sekcja Prime nie obejmuje katalogu streamingu Luna.
Platforma aktywacji jest wyświetlana, jeśli Amazon ją poda; brak terminu jest
jawnie oznaczony. Dostępność Prime dla konkretnego konta i regionu należy
sprawdzić na stronie oferty — język polski zapytania nie gwarantuje dostępności w Polsce.
Bot nie loguje się na konto Amazon ani nie odbiera gier za użytkownika.

Klucz API ani dodatkowa konfiguracja nie są potrzebne. Amazon wymaga anonimowej
sesji (cookies i CSRF), tworzonej wyłącznie w pamięci na czas pobrania katalogu.
Integracja używa wewnętrznego GraphQL publicznej strony, więc zmiany po stronie
Amazon mogą wymagać aktualizacji modułu `prime_games.py`.

Przy ręcznej komendzie oba źródła pobierane są równolegle, z osobnym cache na 15 minut.
Cache znika po restarcie; wygasłe oferty są filtrowane również przy odczycie cache.
Awaria jednego źródła nie blokuje wyników drugiego. Błąd nie jest traktowany jako
brak ofert ani zapisywany w cache. Wyniki trafiają do jednej wiadomości, po pięć kart na stronę. Przyciski
„Poprzednia” i „Następna” zmieniają stronę w tej samej wiadomości. Każdy może
przeglądać wspólną listę. Po pięciu minutach bezczynności przyciski wygasają;
ponowne wywołanie komendy otwiera nową listę.
Bot musi być dodany do serwera z uprawnieniem `applications.commands`.
Komenda jest synchronizowana bezpośrednio na każdym serwerze po starcie bota,
dzięki czemu powinna pojawić się w Discordzie od razu.
Bot musi działać bez przerwy, aby scheduler wykonał publikację o 18:00.

## Codzienne nowe gry na #tvgry

Codziennie o **18:00 Europe/Warsaw** bot pobiera świeże oferty Epic i Amazon
Prime i wysyła na **#tvgry** tylko oferty, których wcześniej tam nie opublikował.
Pierwsze uruchomienie harmonogramu publikuje wszystkie aktualne oferty. Brak
nowości oznacza brak wiadomości. Publikacja używa tej samej paginacji co komenda.
Ręczne `/darmowegry` nadal pokazuje pełną listę i nie zmienia historii powiadomień.

Historia jest zapisywana w SQLite w `data/sent_games.sqlite3`, osobno dla kanału,
źródła i identyfikatora oferty. Zmiana tytułu, daty końca, chwilowy brak oferty
lub restart nie powodują ponownej wysyłki. Historię nieobecnej oferty usuwamy 30 dni po jej wygaśnięciu. Przy braku terminu
usuwamy ją po 90 dniach od pierwszego stwierdzonego braku w poprawnie pobranym
katalogu. Powrót aktywnej oferty zeruje licznik nieobecności, a przedłużenie
promocji aktualizuje datę końca przed sprzątaniem. Błąd źródła nie rozpoczyna
nieobecności i nie usuwa jego historii. Po usunięciu wpisu powracająca oferta
może zostać ogłoszona ponownie. SQLite wykorzystuje zwolnione miejsce przy
kolejnych zapisach; plik nie musi od razu zmniejszać rozmiaru na dysku.

Zapis następuje po potwierdzonej wysyłce. Awaria źródła nie blokuje drugiego,
a błędy trafiają do logów. Uszkodzona historia zatrzymuje publikację zamiast
resetować listę. Przerwanie procesu pomiędzy wysyłką a zapisem może spowodować
powtórzenie wiadomości przy kolejnym sprawdzeniu.

Opcjonalna konfiguracja:
- `DISCORD_GAMES_CHANNEL` — domyślnie `tvgry`, niezależnie od kanału Pepper.
- `DISCORD_GAMES_CHANNEL_ID` — ID kanału gier; ma pierwszeństwo przed nazwą.
  Przy kilku kanałach `tvgry` wymagane jest ID, aby bot nie zgadywał serwera.
- `GAMES_STATE_PATH` — inna ścieżka do pliku SQLite.

Katalog `data/` jest ignorowany przez Git i zachowywany przy standardowym
wdrożeniu. Należy go uwzględnić w kopiach zapasowych i przenosinach serwera;
usunięcie bazy spowoduje ponowną publikację wszystkich aktualnych ofert.
Bot musi działać o 18:00; pominięta publikacja nie jest nadrabiana po restarcie.

## Automatyczne aktualizacje na Mikrusie

Każdy push na `main` uruchamia workflow **Deploy to Mikrus** w GitHub Actions.
Po testach GitHub łączy się przez SSH i uruchamia aktualizator na serwerze.
Aktualizator pobiera najnowszy `main`, ponownie sprawdza zależności i testy,
a następnie restartuje bota. Przy kilku szybkich pushach wdrożenie może objąć
kilka commitów naraz. Wdrożenia nie są wykonywane równolegle.

Wynik jest widoczny w zakładce **Actions** repozytorium. Workflow można też
uruchomić ręcznie przez **Run workflow** dla `main`.
Token Discorda pozostaje w `/etc/chrzaszczbot.env` na serwerze.

### Pierwsza instalacja na Mikrusie 2.1

Poniższe polecenia zakładają świeży Debian/Ubuntu z `systemd`, Pythonem 3.10
lub nowszym i dostępem do repozytorium na GitHubie. Połącz się komendą SSH
z panelu Mikrusa (użyj podanego tam portu):

```bash
ssh root@TWOJ_HOST -p TWOJ_PORT
```

Na serwerze zainstaluj wymagania i pobierz projekt:

```bash
apt-get update
apt-get install -y git python3 python3-venv ca-certificates tzdata util-linux
git clone --branch main https://github.com/zdinozi/ChrzaszczBOT.git /opt/ChrzaszczBOT
```

Jeśli repozytorium jest prywatne, najpierw skonfiguruj dostęp serwera do GitHuba
(np. kluczem deploy key tylko do odczytu i adresem repozytorium SSH).
Nie umieszczaj tokenu GitHuba w adresie repozytorium.

Utwórz plik konfiguracji dostępny wyłącznie dla roota:

```bash
touch /etc/chrzaszczbot.env
chmod 0600 /etc/chrzaszczbot.env
nano /etc/chrzaszczbot.env
```

Wpisz poniższe wartości, zastępując placeholder tokenem bota z Discorda:

```text
DISCORD_TOKEN=WPISZ_TOKEN_BOTA
DISCORD_CHANNEL=promocje
```

Przy ponownej instalacji zachowaj istniejące wartości konfiguracji.
Token pozostaje poza repozytorium.
Jeśli bot działa na starej maszynie, zatrzymaj tam usługę przed uruchomieniem
nowej, aby uniknąć podwójnych publikacji.

Uruchom instalator, który tworzy `.venv`, instaluje zależności, wykonuje testy
i uruchamia lub restartuje bota. Domyślnie wybiera GitHub Actions i wyłącza timer:

```bash
cd /opt/ChrzaszczBOT
sudo bash deploy/install-auto-update.sh
```

### Dostęp GitHub Actions do serwera

W **Settings → Secrets and variables → Actions → Variables** ustaw zmienne
repozytorium (nie sekrety):

| Nazwa | Wartość |
| --- | --- |
| `MIKRUS_HOST` | `wanda202.mikrus.xyz` |
| `MIKRUS_USER` | `root` |
| `MIKRUS_PORT` | `10202` |

Workflow wymaga sekretu repozytorium `MIKRUS_DEPLOY_KEY` zawierającego osobny
prywatny klucz SSH bez hasła. Dodaj go w **Settings → Secrets and variables →
Actions**. Klucza prywatnego nie zapisuj w repozytorium.
Odpowiadający mu klucz publiczny dodaj do `/root/.ssh/authorized_keys` na
Mikrusie, poprzedzając go ograniczeniem:

```text
restrict,command="/usr/local/sbin/chrzaszczbot-deploy" ssh-ed25519 KLUCZ_PUBLICZNY github-actions-chrzaszczbot
```

Ten klucz może uruchamiać wyłącznie aktualizator; nie pozwala na interaktywną
powłokę ani przekierowywanie portów. Skrypt ignoruje polecenie przesłane przez SSH.
Plik `deploy/mikrus_known_hosts` zawiera przypięty publiczny klucz hosta.
Przy zmianie serwera zaktualizuj zmienne połączenia i klucz hosta po jego
niezależnej weryfikacji.

### Diagnostyka i ręczne wdrożenie

```bash
systemctl status chrzaszczbot.service
journalctl -u chrzaszczbot-update.service --since today
sudo /usr/local/sbin/chrzaszczbot-deploy
```

Aktualizator celowo przerywa pracę, jeśli
repozytorium na serwerze zawiera lokalne zmiany albo historia nie pozwala na
bezpieczną aktualizację `fast-forward`.

Alternatywnie można włączyć wcześniejszy tryb odpytywania co 5 minut:

```bash
sudo env DEPLOY_MODE=timer bash deploy/install-auto-update.sh
```

W tym trybie wyłącz workflow w GitHub Actions, aby nie uruchamiać dwóch
mechanizmów wdrożenia jednocześnie.
