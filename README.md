

# gianlucas-gpt-shell

Een simpele, maar slimme shell-assistent voor Linux, geschreven in Python.  
Je typt gewoon wat je wil doen – in het Nederlands – en GPT probeert er het juiste shell-commando van te maken.

Handig als je niet elk terminalcommando vanbuiten kent, maar wel ongeveer weet wat je wil bereiken.

## Functies
- Begrijpt Nederlandstalige opdrachten
- Houdt context bij (zoals vorige commando’s of de huidige map)
- Controleert de opmaak van GPT’s output vóór uitvoering
- Voert precies één geldig shell-commando uit per keer
- Behandelt ook `cd`-commando’s correct (verandert effectief van map)
- Toont uitleg/commentaarregels vóór het uitvoeren van het commando
- Logt commandogeschiedenis en reacties

## Voorbeeld
```
👤 Jij: toon de inhoud van mijn downloadsmap

📝 GPT Commentaar:
# Toont de bestanden in je downloadsmap
--------------------
💻 GPT Commando:
ls -l ~/Downloads
```

## Vereisten
- Python 3.10 of hoger
- OpenAI Python package (`pip install openai`)
- Een geldige `OPENAI_API_KEY` als omgevingsvariabele

## Gebruik
1. Zet je API-key in een omgevingsvariabele:
```bash
export OPENAI_API_KEY="jouw_api_key"
```
2. Start het script:
```bash
python3 gpt_shell.py
```
3. Typ gewone zinnen zoals:
```
maak een map test in mijn documenten
```

## Licentie
MIT-licentie – open source, gebruik het gerust en verbeter het mee!

## Opmerkingen
Dit project is vooral bedoeld voor Nederlandstalige Linux-gebruikers die graag eenvoudiger met de terminal werken, met de kracht van AI achter de hand. 😄

