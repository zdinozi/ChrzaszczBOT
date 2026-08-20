# ChrząszczBOT

Bot Discord publikujący codziennie o 18:00 (czas `Europe/Warsaw`) 10 pierwszych
ofert z rankingu [Pepper Najgorętsze](https://www.pepper.pl/najgoretsze), razem
z ceną, temperaturą, linkiem i zdjęciem każdej okazji.

## Uruchomienie

1. Zainstaluj Python 3.9 lub nowszy i zależności:

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

Po pobraniu projektu do `/opt/ChrzaszczBOT`, utworzeniu środowiska `.venv` oraz
zapisaniu tokenu w `/etc/chrzaszczbot.env` uruchom na Mikrusie:

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
