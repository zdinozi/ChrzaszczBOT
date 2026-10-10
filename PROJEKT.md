# ChrząszczBOT — opis projektu i utrzymanie

Dokument opisuje konfigurację przygotowaną 10 października 2026 r.
Nie zawiera haseł, tokenów ani kluczy prywatnych.

## Co robi bot

ChrząszczBOT publikuje na Discordzie 10 pierwszych ofert ze strony
[Pepper Najgorętsze](https://www.pepper.pl/najgoretsze). Każda oferta zawiera
tytuł, link, a jeśli są dostępne — cenę, temperaturę i zdjęcie.

- Codzienna publikacja odbywa się o **18:00 w strefie Europe/Warsaw**,
  z uwzględnieniem czasu letniego i zimowego.
- Domyślnym kanałem codziennych publikacji jest `promocje`.
- Komenda **`/promocje`** pobiera oferty od razu i odpowiada w miejscu jej
  wywołania; nie korzysta z ustawienia kanału codziennych publikacji.
- Bot musi działać w chwili zaplanowanej publikacji. Nie ma mechanizmu
  odtwarzania publikacji pominiętych podczas przerwy w działaniu.

Projekt nie używa bazy danych, Dockera ani własnego serwera WWW.
Bot łączy się z Discordem i pobiera stronę Pepper przez połączenia wychodzące.

## Jak działa kod

1. `main.py` pobiera token ze zmiennej `DISCORD_TOKEN`. Przy lokalnym
   uruchomieniu może też użyć `token.txt` obok `main.py`.
2. Bot loguje się do Discorda i rejestruje komendę `/promocje` na dostępnych
   serwerach Discorda. Następnie uruchamia harmonogram codziennych publikacji.
3. `pepper_scraper.py` pobiera HTML rankingu Pepper. Pobieranie działa
   w osobnym wątku, aby nie blokować obsługi Discorda; timeout wynosi 20 sekund.
4. Parser szuka ofert w HTML i wybiera pierwsze 10 w kolejności strony.
   Nie sortuje ich samodzielnie według temperatury.
5. `main.py` zamienia oferty w karty Discorda i wysyła wiadomość.

Jeśli pobieranie zawiedzie lub parser znajdzie mniej niż 10 ofert, bot zgłasza
błąd zamiast publikować niepełną listę. Zmiana HTML lub blokada pobierania po
stronie Pepper może wymagać aktualizacji parsera.

## Mapa plików

| Plik | Odpowiedzialność |
| --- | --- |
| `main.py` | Logowanie do Discorda, komenda, harmonogram i format wiadomości. |
| `pepper_scraper.py` | Pobieranie strony i parsowanie ofert. |
| `test_pepper_scraper.py` | Testy parsera na przykładowym HTML, bez sieci. |
| `requirements.txt` | Zależność `discord.py` i dopuszczalny zakres jej wersji. |
| `.github/workflows/deploy.yml` | Testy i wdrożenie po pushu na `main`. |
| `deploy/chrzaszczbot.service` | Usługa systemd uruchamiająca bota. |
| `deploy/chrzaszczbot-update.sh` | Pobranie, sprawdzenie i wdrożenie nowej wersji. |
| `deploy/chrzaszczbot-update.service` | Jednorazowe uruchomienie aktualizatora z blokadą `flock`. |
| `deploy/chrzaszczbot-deploy.sh` | Ograniczony punkt wejścia dla SSH z GitHub Actions. |
| `deploy/install-auto-update.sh` | Instalacja środowiska Pythona i usług na serwerze. |
| `deploy/chrzaszczbot-update.timer` | Opcjonalny stary tryb sprawdzania zmian co 5 minut; obecnie wyłączony. |
| `deploy/mikrus_known_hosts` | Publiczny klucz hosta do weryfikowania serwera podczas SSH. |
| `readme.md` | Instrukcja uruchomienia i instalacji. |

Katalog `docs/` jest ignorowany przez Git. Ten dokument znajduje się w katalogu
głównym, aby można go było wersjonować razem z projektem.

## Gry do odebrania: `/darmowegry`

Komenda pobiera równolegle oferty Epic Games Store dla Polski oraz pełne gry
w ramach Amazon Prime. Sekcja Prime wskazuje wymóg subskrypcji i linkuje do
odbioru w Amazon Luna. Dostępność regionalną potwierdza użytkownik na stronie oferty.
Nie wymaga konta Amazon w konfiguracji bota ani dodatkowych zależności.

- `free_games.py`: wspólny model oferty i osobny cache każdego źródła na 15 minut.
- `epic_games.py`: pobranie i parsowanie promocji Epic.
- `prime_games.py`: anonimowa sesja publicznej strony Amazon (cookies i CSRF),
  następnie zapytanie GraphQL o kolekcję `FREE_GAMES`. Każde żądanie ma timeout
  20 sekund. Cookies i token pozostają w pamięci, nie są zapisywane na dysk.
- `main.py`: jedna wiadomość ze stronami po pięć kart, przyciskami Poprzednia/Następna
  i niezależnymi komunikatami błędów. Nawigacja wygasa po pięciu minutach bezczynności.
- `test_prime_games.py`, `test_free_games.py`: testy parsera, sesji, cache i publikacji.
  `tests/fixtures/prime_games.json` to publiczna odpowiedź katalogu z 10.10.2026,
  ograniczona do pól ofert; nie zawiera cookies, CSRF ani danych konta.

API Amazon jest wewnętrznym API strony i może zmienić format. Błędy GraphQL,
nieprawidłowa struktura lub osiągnięcie limitu 100 rekordów są sygnalizowane jako
błąd źródła, aby nie prezentować potencjalnie niepełnej listy jako kompletnej.
Przy osiągnięciu limitu trzeba dodać paginację zgodną z aktualnym API Amazon.
Nie buforujemy błędów ani nie pokazujemy starego cache po nieudanym odświeżeniu.
Brak daty lub platformy nie powoduje dopisywania zgadywanych informacji.

Testy offline: `python3 -m unittest -q`. Po wdrożeniu sprawdzić `/darmowegry`
na Discordzie, obie sekcje oraz linki odbioru.

## Gdzie działa produkcja

| Element | Konfiguracja |
| --- | --- |
| Repozytorium | https://github.com/zdinozi/ChrzaszczBOT |
| Gałąź wdrażana na produkcję | `main` |
| Serwer | Mikrus 2.1, `wanda202.mikrus.xyz` |
| Port SSH | `10202` |
| System | Ubuntu 24.04, Python 3.12 |
| Katalog aplikacji | `/opt/ChrzaszczBOT` |
| Środowisko Pythona | `/opt/ChrzaszczBOT/.venv` |
| Konfiguracja bota | `/etc/chrzaszczbot.env`, uprawnienia `600`, właściciel `root` |
| Usługa | `chrzaszczbot.service`, obecnie uruchamiana jako `root` |

Systemd uruchamia bota po restarcie serwera i ponawia jego start po zakończeniu
procesu. Kod z repozytorium jest wykonywany na serwerze jako root, więc dostęp
do wysyłania zmian na `main` oznacza możliwość zmiany zachowania produkcji.

## Wdrażanie po pushu

```text
Zmiana na Macu → commit → push na main
                           ↓
                    GitHub Actions
                    testy i kontrola składni
                           ↓ SSH
                    Mikrus: aktualizator
                    pobranie main → testy → restart bota
```

1. Push na `main` uruchamia workflow **Deploy to Mikrus**.
2. GitHub instaluje zależności, uruchamia testy parsera i sprawdza składnię
   plików Pythona oraz skryptów Bash.
3. Po powodzeniu łączy się z Mikrusem przez SSH za pomocą osobnego klucza.
4. Serwer wymusza uruchomienie `/usr/local/sbin/chrzaszczbot-deploy`.
   Skrypt uruchamia usługę aktualizatora i czeka na jej zakończenie.
5. Aktualizator pobiera najnowszy `origin/main`. Odrzuca zmiany lokalne
   w śledzonych plikach i historię, której nie da się zaktualizować fast-forward.
6. Nowy kod sprawdza w tymczasowym katalogu z osobnym środowiskiem Pythona.
   Dopiero po testach aktualizuje katalog aplikacji, instaluje zależności
   i restartuje bota.
7. Skrypt wdrożenia po 5 sekundach sprawdza, czy usługa bota jest aktywna.

Wdrożenia workflow są kolejkowane; uruchomione wdrożenie nie jest anulowane
przez kolejny push. Aktualizator pobiera najnowszy `main`, więc przy szybkiej
serii pushów może wdrożyć kilka commitów naraz. Nie przypina wdrożenia do SHA
konkretnego uruchomienia Actions. Blokada `flock` dodatkowo chroni przed
jednoczesnym działaniem kilku aktualizatorów na serwerze.

Wyniki: [GitHub Actions](https://github.com/zdinozi/ChrzaszczBOT/actions).
Można też wybrać **Deploy to Mikrus → Run workflow → main**.
Timer odpytywania co 5 minut jest wyłączony.

Adres SSH nie jest wpisany na stałe w workflow. Dane połączenia są zmiennymi
repozytorium w **Settings → Secrets and variables → Actions → Variables**:
`MIKRUS_HOST=wanda202.mikrus.xyz`, `MIKRUS_USER=root`, `MIKRUS_PORT=10202`.
Workflow przekazuje je do kroku SSH jako zmienne środowiskowe. Nie są sekretami;
prywatny klucz pozostaje w **Secrets** jako `MIKRUS_DEPLOY_KEY`.
Zmiana serwera wymaga również aktualizacji zweryfikowanego klucza hosta
w `deploy/mikrus_known_hosts`.

Aktualizator nie wykonuje automatycznego rollbacku. Błąd podczas końcowej
instalacji zależności lub startu wymaga interwencji. Zielony workflow oznacza
przejście testów i aktywny proces, ale nie sprawdza wysłania wiadomości ani
aktualnej dostępności Pepper. Test funkcjonalny wykonuje się komendą `/promocje`.

## Token, hasło i klucze — czym się różnią

| Dane | Do czego służą | Gdzie są używane |
| --- | --- | --- |
| Hasło roota Mikrusa | Ręczne logowanie administracyjne. | Wpisujesz je przy logowaniu hasłem; Actions go nie używa. |
| Twój klucz `~/.ssh/mikrus` | Logowanie z Maca. | Prywatny na Macu, publiczny na Mikrusie. |
| Sekret `MIKRUS_DEPLOY_KEY` | Połączenie Actions z Mikrusem. | Prywatny w GitHub Actions Secrets, publiczny na Mikrusie. |
| `DISCORD_TOKEN` | Logowanie bota do Discorda. | W chronionym pliku środowiskowym na Mikrusie. |
| `deploy/mikrus_known_hosts` | Potwierdzenie tożsamości serwera SSH. | W repozytorium; zawiera dane publiczne. |

Klucz Actions jest osobną parą Ed25519, wygenerowaną na Macu w katalogu
tymczasowym. Nie jest kopią Twojego klucza osobistego. Klucz prywatny został
zaszyfrowany kluczem publicznym GitHuba i przesłany do API sekretów repozytorium.
Po udanym wdrożeniu jego tymczasową kopię prywatną na Macu usunięto.

Na Mikrusie klucz publiczny Actions ma w `/root/.ssh/authorized_keys` wymuszone
polecenie aktualizatora i opcję `restrict`: nie daje interaktywnego terminala
ani przekierowywania portów. To ograniczenie dotyczy połączenia SSH; nie jest
izolacją kodu wdrażanego z `main`.

Sekret jest widoczny z nazwy w **Settings → Secrets and variables → Actions**.
GitHub nie pokazuje jego zapisanej wartości. Zmiana klucza wymaga nowej pary:
nowego sekretu na GitHubie i odpowiadającego mu klucza publicznego na Mikrusie.

Token Discorda nie jest przesyłany przez workflow. Systemd wczytuje go z
`/etc/chrzaszczbot.env` przy starcie procesu. Aktualizacja kodu zachowuje ten plik.

## Konfiguracja bota

| Zmienna | Znaczenie |
| --- | --- |
| `DISCORD_TOKEN` | Token bota wymagany do logowania. |
| `DISCORD_CHANNEL` | Nazwa kanału codziennych publikacji; domyślnie `promocje`. |
| `DISCORD_CHANNEL_ID` | Opcjonalne ID kanału; ma pierwszeństwo, jeśli wskazuje dostępny kanał tekstowy. |
| `LOG_LEVEL` | Poziom logowania; domyślnie `INFO`. |

Jeśli ID nie wskazuje dostępnego kanału tekstowego, bot szuka kanału po nazwie.
Przy kilku serwerach Discorda najpewniejsze jest podanie ID docelowego kanału.
Godzina publikacji jest ustawiona w kodzie, w `POST_TIME` w `main.py`.

## Codzienna obsługa

Po zmianie kodu na Macu sprawdź i wyślij wybrane pliki:

```bash
python3 -m unittest -q
git status
git add NAZWA_ZMIENIONEGO_PLIKU
git commit -m "Opis zmiany"
git push origin main
```

Do obsługi serwera połącz się z Maca:

```bash
ssh -i ~/.ssh/mikrus -p 10202 root@wanda202.mikrus.xyz
```

Poniższe polecenia wykonuj już na Mikrusie:

```bash
# Stan i logi bota
systemctl status chrzaszczbot --no-pager
journalctl -u chrzaszczbot -n 100 --no-pager

# Logi wdrożeń i wersja kodu
journalctl -u chrzaszczbot-update.service -n 50 --no-pager
git -C /opt/ChrzaszczBOT rev-parse --short HEAD

# Restart bez zmiany kodu
systemctl restart chrzaszczbot

# Ręczne pobranie i wdrożenie main
/usr/local/sbin/chrzaszczbot-deploy

# Edycja konfiguracji; po zapisaniu potrzebny jest restart bota
nano /etc/chrzaszczbot.env
systemctl restart chrzaszczbot
```

Zmiany plików usług i skryptów w `deploy/` trafiają do katalogu repozytorium,
ale zwykły aktualizator nie kopiuje ich ponownie do `/etc/systemd/system`
i `/usr/local/sbin`. Po zmianie tych plików uruchom na serwerze instalator:

```bash
cd /opt/ChrzaszczBOT
bash deploy/install-auto-update.sh
```

## Gdy coś nie działa

- **Czerwony workflow:** sprawdź krok, który zawiódł, w GitHub Actions.
  Przy błędzie SSH sprawdź sekret wdrożeniowy, klucz publiczny na serwerze
  i przypięty klucz hosta. Nie wyłączaj weryfikacji tożsamości serwera.
- **Bot offline:** sprawdź status i logi usługi. Po zmianie tokenu zrestartuj bota.
- **Brak codziennej wiadomości:** sprawdź kanał, uprawnienia bota, logi
  i to, czy proces działał o 18:00 czasu Warszawy.
- **Błąd pobierania ofert:** sprawdź komunikat parsera/pobierania w logach;
  testy na przykładowym HTML nie wykrywają zmian na żywej stronie Pepper.
- **Potrzebne cofnięcie zmiany:** utwórz commit cofający przez `git revert`
  i wyślij go na `main`. Aktualizator wymaga historii fast-forward,
  więc nie używaj force-pusha do cofania produkcji.

Nie wklejaj sekretów do zgłoszeń, logów diagnostycznych ani dokumentacji.
Instrukcja pierwszej instalacji znajduje się w [readme.md](readme.md).
