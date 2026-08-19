# ChrząszczBOT

Bot Discord publikujący codziennie o 18:00 (czas `Europe/Warsaw`) 10 pierwszych
ofert z rankingu [Pepper Najgorętsze](https://www.pepper.pl/najgoretsze).

## Uruchomienie

1. Zainstaluj Python 3.9 lub nowszy i zależności:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

2. Ustaw token bota w zmiennej `DISCORD_TOKEN` albo umieść go w lokalnym pliku
   `token.txt` (plik jest ignorowany przez Git).

3. W Discord Developer Portal włącz dla bota **Message Content Intent**.

4. Uruchom:

   ```bash
   python3 main.py
   ```

Domyślnie bot publikuje na pierwszym znalezionym kanale tekstowym `main`.
Można to zmienić zmienną `DISCORD_CHANNEL` lub, dokładniej, ustawić
`DISCORD_CHANNEL_ID` na numeryczne ID kanału.

Komenda `$deale` publikuje ranking od razu i służy do ręcznego testowania.
Bot musi działać bez przerwy, aby scheduler wykonał publikację o 18:00.
