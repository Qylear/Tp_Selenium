from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_user_input():
    speciality = input("Spécialité (ex: généraliste): ")
    location = input("Ville ou code postal: ")
    
    print("\nFiltre par secteur:")
    print("1. Tous les secteurs")
    print("2. Secteur 1 uniquement")
    print("3. Secteur 2 uniquement")
    print("4. Conventionné uniquement")
    
    sector_choice = input("Choisissez une option (1-4) [défaut: 1]: ").strip()
    if not sector_choice:
        sector_choice = "1"
    
    sector_filter = {
        "1": "tous",
        "2": "secteur 1",
        "3": "secteur 2", 
        "4": "conventionné"
    }.get(sector_choice, "tous")
    
    visio_filter = input("\nFiltrer uniquement les médecins avec visio disponible? (o/n) [défaut: n]: ").strip().lower()
    visio_only = visio_filter in ['o', 'oui', 'y', 'yes']
    
    return speciality, location, sector_filter, visio_only

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)
    return driver, wait

def handle_cookies(wait):
    try:
        cookie_selectors = [
            "#didomi-notice-disagree-button",
            "button[aria-label='Refuser']",
            "button:contains('Refuser')",
            ".didomi-continue-without-agreeing"
        ]
        
        for selector in cookie_selectors:
            try:
                reject_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                reject_btn.click()
                logger.info("Cookies refusés.")
                return
            except:
                continue
        
        logger.info("Aucune bannière cookies trouvée ou déjà traitée.")
    except:
        logger.info("Aucune bannière cookies trouvée.")

def search_doctors(driver, wait, speciality, location):
    driver.get("https://www.doctolib.fr")
    time.sleep(2)
    handle_cookies(wait)
    
    try:
        place_selectors = [
            "input.searchbar-place-input",
            "input[placeholder*='Où']",
            "input[data-test-id='location-input']"
        ]
        
        place_input = None
        for selector in place_selectors:
            try:
                place_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                break
            except:
                continue
                
        if place_input:
            place_input.clear()
            place_input.send_keys(location)
            time.sleep(1)
        
        speciality_selectors = [
            "input.searchbar-query-input",
            "input[placeholder*='spécialité']",
            "input[data-test-id='speciality-input']"
        ]
        
        speciality_input = None
        for selector in speciality_selectors:
            try:
                speciality_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                break
            except:
                continue
                
        if speciality_input:
            speciality_input.clear()
            speciality_input.send_keys(speciality)
            time.sleep(1)
        
        submit_selectors = [
            "button.searchbar-submit-button",
            "button[type='submit']",
            "button:contains('Rechercher')"
        ]
        
        submit_btn = None
        for selector in submit_selectors:
            try:
                submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                break
            except:
                continue
                
        if submit_btn:
            submit_btn.click()
            time.sleep(5)
        
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")

def extract_doctor_info(card):
    try:
        name = ""
        name_selectors = [
            "h2.dl-text.dl-text-body.dl-text-bold.dl-text-s.dl-text-primary-110",
            "h2[data-design-system-component='Text']",
            ".dl-text-bold",
            "h2"
        ]
        
        for selector in name_selectors:
            try:
                name_element = card.find_element(By.CSS_SELECTOR, selector)
                name = name_element.text.strip()
                if name:
                    break
            except:
                continue
        
        address = ""
        sector = ""
        availability = ""
        
        paragraph_selectors = [
            "p.XZWvFVZmM9FHf461kjNO.G5dSlmEET4Zf5bQ5PR69",
            "p[data-design-system-component='Paragraph']",
            ".dl-text-regular",
            "p"
        ]
        
        paragraphs = []
        for selector in paragraph_selectors:
            try:
                paragraphs = card.find_elements(By.CSS_SELECTOR, selector)
                if paragraphs:
                    break
            except:
                continue
        
        for p in paragraphs:
            try:
                text = p.text.strip()
                if not text:
                    continue
                    
                if "Secteur" in text or "€" in text or "Conventionné" in text:
                    sector = text
                elif "Disponibilité" in text or "disponible" in text or "prochaine" in text:
                    availability = text
                elif any(word in text.lower() for word in ["rue", "avenue", "boulevard", "place", "chemin", "allée"]):
                    address = text
                elif text.replace(" ", "").isdigit() and len(text) == 5:
                    if not address:
                        address = text
                    else:
                        address += f" {text}"
            except:
                continue
        
        if not address:
            try:
                location_elements = card.find_elements(By.CSS_SELECTOR, "span[class*='location'], span[class*='address'], .dl-text-neutral-090")
                for elem in location_elements:
                    text = elem.text.strip()
                    if text and not text.isdigit():
                        address = text
                        break
            except:
                pass
        
        specialty = ""
        try:
            specialty_elements = card.find_elements(By.CSS_SELECTOR, "p[style*='oxygen-color-component-text-bodyText-neutral-weak']")
            for elem in specialty_elements:
                text = elem.text.strip()
                if text and "Médecin" in text:
                    specialty = text
                    break
        except:
            pass
        
        visio_status = "visio non dispo"
        try:
            visio_indicators = [
                "svg[data-icon-name='video/video']",
                "svg[data-icon-name='video']", 
                ".video-icon",
                "[aria-label*='vidéo']",
                "[aria-label*='Vidéo']",
                "svg[viewBox='0 0 16 16'][fill='currentColor']",
                "*[class*='video']",
                "*[title*='vidéo']",
                "*[title*='Vidéo']"
            ]
            
            for selector in visio_indicators:
                try:
                    visio_elements = card.find_elements(By.CSS_SELECTOR, selector)
                    for elem in visio_elements:
                        if elem.is_displayed():
                            if elem.tag_name.lower() == 'svg':
                                viewbox = elem.get_attribute('viewBox')
                                if viewbox == '0 0 16 16':
                                    visio_status = "visio dispo"
                                    break
                            
                            aria_label = elem.get_attribute('aria-label') or ""
                            title = elem.get_attribute('title') or ""
                            if any(word in (aria_label + title).lower() for word in ['vidéo', 'video', 'visio']):
                                visio_status = "visio dispo"
                                break
                            
                            class_attr = elem.get_attribute('class') or ""
                            if 'video' in class_attr.lower():
                                visio_status = "visio dispo"
                                break
                    
                    if visio_status == "visio dispo":
                        break
                except:
                    continue
            
            if visio_status == "visio non dispo":
                all_text = card.text.lower()
                if any(word in all_text for word in ['visio', 'vidéo', 'téléconsultation', 'video']):
                    visio_status = "visio dispo"
                    
        except Exception as e:
            logger.debug(f"Erreur lors de la vérification visio: {e}")
            pass

        return {
            'name': name,
            'specialty': specialty,
            'address': address,
            'sector': sector,
            'availability': availability,
            'visio': visio_status
        }
        
    except Exception as e:
        logger.error(f"Erreur d'extraction: {e}")
        return None

def filter_doctors(doctors, sector_filter, visio_only):
    filtered_doctors = []
    
    for doctor in doctors:
        if not doctor or not doctor.get('name'):
            continue
            
        sector_match = True
        if sector_filter != "tous":
            doctor_sector = (doctor.get('sector') or "").lower()
            
            if sector_filter == "secteur 1":
                sector_match = "secteur 1" in doctor_sector or "secteur1" in doctor_sector
            elif sector_filter == "secteur 2":
                sector_match = "secteur 2" in doctor_sector or "secteur2" in doctor_sector
            elif sector_filter == "conventionné":
                sector_match = "conventionné" in doctor_sector or "convention" in doctor_sector
        
        visio_match = True
        if visio_only:
            visio_match = doctor.get('visio') == "visio dispo"
        
        if sector_match and visio_match:
            filtered_doctors.append(doctor)
            
    return filtered_doctors

def save_to_csv(doctors, sector_filter, visio_only):
    filename_parts = ["doctors"]
    
    if sector_filter != "tous":
        filename_parts.append(sector_filter.replace(" ", "_"))
    
    if visio_only:
        filename_parts.append("avec_visio")
    
    filename = "_".join(filename_parts) + ".csv"
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'specialty', 'address', 'sector', 'availability', 'visio'])
        writer.writeheader()
        valid_doctors = [doc for doc in doctors if doc and doc.get('name')]
        for doc in valid_doctors:
            writer.writerow(doc)
    
    logger.info(f"{len(valid_doctors)} médecins sauvegardés dans {filename}")

def main():
    try:
        speciality, location, sector_filter, visio_only = get_user_input()
        driver, wait = setup_driver()
        
        search_doctors(driver, wait, speciality, location)
        
        cards = []
        result_selectors = [
            ".dl-search-result",
            ".search-result",
            "[data-test-id='search-result']",
            ".dl-card"
        ]
        
        for selector in result_selectors:
            try:
                cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                if cards:
                    break
            except:
                continue
        
        if not cards:
            logger.warning("Aucun résultat trouvé. Vérifiez les termes de recherche.")
            return
            
        logger.info(f"{len(cards)} résultats trouvés.")
        
        doctors = []
        for i, card in enumerate(cards[:20]):
            try:
                info = extract_doctor_info(card)
                if info and info.get('name'):
                    logger.info(f"Médecin {i+1}: {info}")
                    doctors.append(info)
                else:
                    logger.warning(f"Impossible d'extraire les infos de la carte {i+1}")
            except Exception as e:
                logger.error(f"Erreur avec la carte {i+1}: {e}")
                continue
        
        if doctors:
            filtered_doctors = filter_doctors(doctors, sector_filter, visio_only)
            
            logger.info(f"Filtres appliqués:")
            logger.info(f"- Secteur: {sector_filter}")
            logger.info(f"- Visio uniquement: {'Oui' if visio_only else 'Non'}")
            logger.info(f"Résultats: {len(filtered_doctors)}/{len(doctors)} médecins correspondent aux critères")
            
            if filtered_doctors:
                save_to_csv(filtered_doctors, sector_filter, visio_only)
                
                print(f"\n=== RÉSUMÉ DES RÉSULTATS FILTRÉS ===")
                for i, doctor in enumerate(filtered_doctors, 1):
                    print(f"{i}. {doctor['name']}")
                    if doctor['specialty']:
                        print(f"   Spécialité: {doctor['specialty']}")
                    if doctor['sector']:
                        print(f"   Secteur: {doctor['sector']}")
                    print(f"   Visio: {doctor['visio']}")
                    if doctor['address']:
                        print(f"   Adresse: {doctor['address']}")
                    print()
            else:
                logger.warning("Aucun médecin ne correspond aux critères de filtrage spécifiés.")
                print("\n💡 Suggestions:")
                print("- Essayez de modifier les filtres (secteur ou visio)")
                print("- Vérifiez si la spécialité ou la localisation sont correctes")
        else:
            logger.warning("Aucune donnée de médecin extraite.")
            
    except ModuleNotFoundError as e:
        logger.error(f"Module manquant : {e}. Installez avec: pip install selenium webdriver-manager")
    except Exception as e:
        logger.error(f"Erreur générale : {e}")
    finally:
        try:
            driver.quit()
        except:
            logger.warning("Le navigateur n'a pas pu être fermé correctement.")

if __name__ == "__main__":
    main()
