# ChrząszczBOT

Bot Discord publikujący codziennie o 18:00 (czas `Europe/Warsaw`) 10 pierwszych
ofert z rankingu [Pepper Najgorętsze](https://www.pepper.pl/najgoretsze), razem
z ceną, temperaturą, linkiem i zdjęciem każdej okazji.

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
Bot musi być dodany do serwera z uprawnieniem `applications.commands`.
Komenda jest synchronizowana bezpośrednio na każdym serwerze po starcie bota,
dzięki czemu powinna pojawić się w Discordzie od razu.
Bot musi działać bez przerwy, aby scheduler wykonał publikację o 18:00.

## Automatyczne aktualizacje na Mikrusie

Repozytorium zawiera timer `systemd`, który co 5 minut sprawdza gałąź `main` na
GitHubie. Nowa wersja jest instalowana i restartuje bota dopiero po pomyślnym
zainstalowaniu zależności oraz przejściu testów.

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
i uruchamia lub restartuje bota oraz włącza timer aktualizacji:

```bash
cd /opt/ChrzaszczBOT
sudo bash deploy/install-auto-update.sh
```

Stan timera i logi aktualizacji:

```bash
systemctl status chrzaszczbot-update.timer
journalctl -u chrzaszczbot-update.service --since today
```

Od tej chwili wystarczy wysłać zmiany do `main` na GitHubie. Mikrus wdroży je
automatycznie w ciągu około 5 minut. Aktualizator celowo przerywa pracę, jeśli
repozytorium na serwerze zawiera lokalne zmiany albo historia nie pozwala na
bezpieczną aktualizację `fast-forward`.
