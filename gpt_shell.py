import openai
import subprocess
import re # Nodig voor de eerste-regel check
import os
import sys
import time

# --- Bepaal Home Directory Dynamisch ---
try:
    # Verkrijg de thuisdirectory van de huidige gebruiker
    user_home_dir = os.path.expanduser("~")
    if not user_home_dir or not os.path.isdir(user_home_dir):
        # Fallback als detectie mislukt (onwaarschijnlijk op Linux/macOS)
        user_home_dir = "/home/gebruiker" # Generieke fallback
        print(f"⚠️ Kon thuisdirectory niet automatisch detecteren, gebruik generieke '{user_home_dir}'")
except Exception as e:
    user_home_dir = "/home/gebruiker" # Generieke fallback bij fout
    print(f"⚠️ Fout bij detecteren thuisdirectory ({e}), gebruik generieke '{user_home_dir}'")

# OpenAI setup
from openai import OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ Fout: Omgevingsvariabele OPENAI_API_KEY niet gevonden.")
    print("Zorg ervoor dat je de API-key hebt ingesteld, bijvoorbeeld met:")
    print("export OPENAI_API_KEY='jouw_api_key_hier'")
    sys.exit(1)

client = OpenAI(api_key=api_key)

MODEL = "gpt-4o" # Of een ander model naar keuze

# --- Systeemboodschap v6.4 Template (Context-Aware + Dynamic Home Dir) ---
# Gebruikt een placeholder {user_home_dir} die later wordt ingevuld
deep_system_msg_template = (
    "Je bent een geavanceerde Linux-shellassistent. De gebruiker typt opdrachten in gewone taal.\n"
    "BELANGRIJKE INFORMATIE VOOR CONTEXT:\n"
    "- De thuisdirectory van de gebruiker is '{user_home_dir}'. Gebruik '~' of dit pad waar nodig.\n" # Placeholder
    "\n"
    "STRIKTE REGELS VOOR OUTPUT FORMAT:\n"
    "1. BEGIN ALTIJD MET EEN COMMANDO OF EEN '#'-REGEL. Geen uitzonderingen.\n"
    "2. Gebruik '#' voor ALLE uitleg, commentaar, vragen, of stappenplannen.\n"
    "3. Elke regel die GEEN uitvoerbaar commando is, MOET met '#' beginnen.\n"
    "4. Geef MAXIMAAL ÉÉN uitvoerbaar bash-commando per antwoord.\n"
    "5. Als je een commando geeft, moet dit de EERSTE regel zijn die NIET met '#' begint.\n"
    "6. Gebruik GEEN ```bash``` of andere markdown.\n"
    "7. LET OP DE CONTEXT: De historie bevat berichten van 'user' en 'assistant'. De 'assistant' berichten bevatten soms jouw vorige antwoord (commando/commentaar) GEVOLGD DOOR de output/foutmelding van dat commando, beginnend met '[Command Output]' of '[Command Error]'. Gebruik deze informatie om vervolgstappen correct uit te voeren (bv. gebruik gevonden apparaatnamen of paden).\n"
    "\n"
    "--- Voorbeeld CORRECT Antwoord (Commando eerst): ---\n"
    "ls -l ~\n"
    "# Dit toont de bestanden in de thuisdirectory.\n" # Generiek voorbeeld
    "\n"
    "--- Voorbeeld CORRECT Antwoord (Commentaar eerst): ---\n"
    "# Ik zoek naar downloads in de thuisdirectory.\n"
    "find ~/Downloads -name '*.zip'\n" # Generiek voorbeeld met ~
    "\n"
    "Houd je hier STRIKT aan!"
)

# Formatteer de systeemboodschap één keer met de gedetecteerde home directory
formatted_deep_system_msg = deep_system_msg_template.format(user_home_dir=user_home_dir)

print("🤖 GPT Shell gestart (Context-modus v6.4 - Anoniem). Typ een taak (of 'stop').\n")
print(f"ℹ️ Gedetecteerde thuisdirectory voor deze sessie: {user_home_dir}") # Informeer gebruiker

# Contextgeschiedenis
context_log = []
# Aantal user/assistant paren om te bewaren
MAX_HISTORY_PAIRS = 5
COMMAND_TIMEOUT = 60

while True:
    try:
        prompt = input("👤 Jij: ")
        if prompt.lower() in ["stop", "exit", "quit", "einde"]:
            print("👋 Tot ziens!")
            break
        if not prompt:
            continue

        # Bereid berichten voor GPT voor (beperk contextlengte)
        history_limit = MAX_HISTORY_PAIRS * 2 # Max user + assistant messages
        messages = [
            # Gebruik de reeds geformatteerde systeemboodschap
            {"role": "system", "content": formatted_deep_system_msg},
        ] + context_log[-history_limit:] + [
            {"role": "user", "content": prompt}
        ]

        # Roep de OpenAI API aan
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4
        )

        raw_response = response.choices[0].message.content.strip()

        # --- Verwerkingslogica ---
        comment_lines = []
        command_line = None
        valid_response_format = False
        first_line_checked = False
        rejected_response = False

        lines = raw_response.splitlines()
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue

            if not first_line_checked:
                first_line_checked = True
                if stripped_line.startswith('#'):
                    valid_response_format = True
                    comment_lines.append(stripped_line)
                # Check of het op commando lijkt (regex accepteert ~)
                elif re.match(r"^[a-zA-Z0-9/_\.~-]+", stripped_line):
                    valid_response_format = True
                    command_line = stripped_line
                else:
                    valid_response_format = False
                    rejected_response = True
                    print(f"\n❌ Fout: GPT antwoord had ongeldige opmaak.")
                    print(f"   (Antwoord begon met: '{stripped_line[:70]}...')")
                    print(f"   (Antwoord moet beginnen met '#' of een geldig commando).")
                    break

            elif valid_response_format:
                if stripped_line.startswith('#'):
                    comment_lines.append(stripped_line)
                elif command_line is None:
                    command_line = stripped_line
                else:
                    if stripped_line.startswith('#'):
                        comment_lines.append(stripped_line)
                    else:
                        print(f"⚠️ Waarschuwing: Extra regel genegeerd: '{stripped_line}'")
        # --- Einde Verwerkingslogica ---

        processed_gpt_response = ""
        execution_result_str = ""
        command_was_run = False # Houd bij of een commando (cd of ander) is geprobeerd

        # Verwerk alleen verder als het format geldig was
        if valid_response_format:
            processed_gpt_response = "\n".join(comment_lines + ([command_line] if command_line else []))

            if comment_lines:
                print("\n📝 GPT Commentaar:")
                for comment in comment_lines:
                    print(comment)
                print("-" * 20)

            # Controleer of er een commando is om uit te voeren
            if command_line:
                 if not command_line.strip():
                     print("🤔 GPT gaf een lege regel als commando.")
                     command_line = None

            # --- Commando Uitvoering ---
            if command_line:
                command_was_run = True # Markeer dat we een commando proberen

                # --- Speciale behandeling voor 'cd' ---
                if command_line.startswith("cd "):
                    target_dir = command_line[3:].strip()
                    if not target_dir: target_dir = "~" # 'cd' zonder argument gaat naar home
                    # Breid '~' en omgevingsvariabelen uit
                    target_dir_expanded = os.path.expanduser(os.path.expandvars(target_dir))

                    print(f"💿 Poging tot wisselen naar map: {target_dir_expanded}")
                    print("-" * 20)
                    try:
                        os.chdir(target_dir_expanded)
                        new_cwd = os.getcwd()
                        success_msg = f"✅ Huidige map gewijzigd naar: {new_cwd}"
                        print(success_msg)
                        execution_result_str = f"[Directory Changed]\nNieuwe map: {new_cwd}\n"
                    except FileNotFoundError:
                        error_msg = f"❌ Fout: Directory niet gevonden: {target_dir_expanded}"
                        print(error_msg)
                        execution_result_str = f"[Command Error]\n{error_msg}\n"
                    except Exception as cd_e:
                        error_msg = f"❌ Fout bij wisselen van map naar '{target_dir_expanded}': {cd_e}"
                        print(error_msg)
                        execution_result_str = f"[Command Error]\n{error_msg}\n"
                    print("-" * 20)

                # --- Andere commando's uitvoeren via subprocess ---
                else:
                    print(f"💻 GPT Commando:\n{command_line}\n")
                    print("🚀 Uitvoeren...")
                    print("-" * 20)
                    try:
                        # shell=True is nodig voor pipes, redirects, en expandeert '~'
                        process = subprocess.run(
                            command_line,
                            shell=True, text=True, capture_output=True, timeout=COMMAND_TIMEOUT,
                            # Voer uit in de huidige werkdirectory van het script
                            cwd=os.getcwd()
                        )

                        # Toon output/error aan gebruiker
                        if process.stdout: print("✅ Output:\n" + process.stdout.strip())
                        if process.stderr: print("❌ Foutmelding (stderr):\n" + process.stderr.strip())
                        if not process.stdout and not process.stderr and process.returncode == 0: print("✅ Commando succesvol uitgevoerd (geen output).")
                        elif process.returncode != 0 and not process.stderr: print(f"⚠️ Commando uitgevoerd met exit code {process.returncode} (geen stderr).")
                        print("-" * 20)

                        # Bereid output/error voor context log string
                        if process.stdout:
                            execution_result_str += "[Command Output]\n" + process.stdout.strip() + "\n"
                        if process.stderr:
                            execution_result_str += "[Command Error]\n" + process.stderr.strip() + "\n"
                        if not execution_result_str and process.returncode == 0:
                             execution_result_str = "[Command Executed Successfully - No Output]\n"
                        elif not execution_result_str and process.returncode != 0:
                             execution_result_str = f"[Command Failed - Exit Code {process.returncode} - No Output]\n"

                    except subprocess.TimeoutExpired:
                        error_msg = f"❌ Fout: Commando duurde langer dan {COMMAND_TIMEOUT} seconden."
                        print(error_msg)
                        print("-" * 20)
                        execution_result_str = f"[Command Error]\n{error_msg}\n"
                    except Exception as exec_e:
                        error_msg = f"❌ Fout tijdens uitvoeren commando '{command_line}': {exec_e}"
                        print(error_msg)
                        print("-" * 20)
                        execution_result_str = f"[Command Error]\n{error_msg}\n"
            # --- Einde Commando Uitvoering ---

            elif not comment_lines:
                 # Geldig format, maar geen commando en geen commentaar
                 print("🤔 GPT gaf geen commando of commentaar terug.")
                 print("-" * 20)
                 processed_gpt_response = "# Geen commando of commentaar ontvangen."

        # --- Context Logging ---
        context_log.append({"role": "user", "content": prompt})
        if rejected_response:
             context_log.append({"role": "assistant", "content": "# FOUT: GPT gaf een antwoord met ongeldige opmaak."})
        else:
             full_assistant_content_for_log = processed_gpt_response
             # Voeg uitvoeringsresultaat toe als er een commando is geprobeerd
             if command_was_run and execution_result_str:
                 full_assistant_content_for_log += "\n\n" + execution_result_str.strip()
             context_log.append({"role": "assistant", "content": full_assistant_content_for_log})
        # --- Einde Context Logging ---

        # Zorg dat de context log niet te lang wordt
        history_limit = MAX_HISTORY_PAIRS * 2 # Max user + assistant messages
        while len(context_log) > history_limit:
            context_log.pop(0) # Verwijder oudste bericht (user of assistant)

    # --- Exception Handling ---
    except openai.APIError as e:
        if "406" in str(e): print(f"❌ OpenAI API Fout (406): Probleem met berichtstructuur. {e}")
        else: print(f"❌ OpenAI API Fout: {e}")
        time.sleep(1)
    except openai.AuthenticationError as e:
         print(f"❌ OpenAI Authenticatie Fout: Controleer je API key. {e}")
         break
    except openai.RateLimitError as e:
         print(f"❌ OpenAI Rate Limiet Fout: Te veel verzoeken. Wacht even. {e}")
         time.sleep(5)
    except Exception as e:
        print(f"❌ Onverwachte Fout: {e}")
        # import traceback # Uncomment voor debuggen
        # traceback.print_exc() # Uncomment voor debuggen
        print("-" * 20)
    # --- Einde Exception Handling ---

    print("") # Lege regel

