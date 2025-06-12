from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import csv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_user_input():
    speciality = input("Entrez la spécialité recherchée (ex: dermatologue): ")
    location = input("Entrez le code postal ou la ville: ")
    
    # Ask about filters
    want_filters = input("Voulez-vous des filtres en plus ? (o/n) : ").lower()
    filters = {}
    
    if want_filters in ['o', 'oui']:
        # Ask about video consultation
        want_video = input("Voulez-vous uniquement des consultations en visio ? (o/n) : ").lower()
        filters['video'] = want_video in ['o', 'oui']
        
        # Ask about insurance sector
        want_insurance = input("Voulez-vous filtrer par type d'assurance ? (o/n) : ").lower()
        if want_insurance in ['o', 'oui']:
            print("\nTypes d'assurance disponibles:")
            print("1 - Secteur 1")
            print("2 - Secteur 2")
            print("0 - Non conventionné")
            sector = input("\nEntrez le numéro correspondant au secteur souhaité (0, 1 ou 2) : ")
            while sector not in ['0', '1', '2']:
                print("Erreur: Veuillez entrer 0, 1 ou 2")
                sector = input("Entrez le numéro correspondant au secteur souhaité (0, 1 ou 2) : ")
            filters['sector'] = sector
    
    return speciality, location, filters

def setup_driver():
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get("https://www.doctolib.fr/")
    wait = WebDriverWait(driver, 10)
    return driver, wait

def handle_cookies(wait):
    try:
        reject_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "didomi-notice-disagree-button"))
        )
        reject_btn.click()
        wait.until(EC.invisibility_of_element_located((By.ID, "didomi-notice-disagree-button")))
    except:
        pass

def search_doctors(driver, wait, speciality, location, filters=None):
    try:
        # Enter location
        place_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                "input.searchbar-input.searchbar-place-input"))
        )
        place_input.clear()
        place_input.send_keys(location)
        time.sleep(1)
        
        # Enter speciality
        speciality_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                "input.searchbar-input.searchbar-query-input"))
        )
        speciality_input.clear()
        speciality_input.send_keys(speciality)
        time.sleep(1)
        
        # Click search button
        search_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,
                "button.Tappable-inactive.dl-button-primary.searchbar-submit-button.dl-button.dl-button-size-medium"))
        )
        search_button.click()
        time.sleep(3)  # Wait for results to load
        
        # Handle filters if any
        if filters:
            try:
                # Wait for and click filter button
                filter_button = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR,
                        "button.inline-flex.dl-align-items-center.h-fit.dl-rounded-borders-lg.dl-pill-white.dl-pill-medium.dl-pill-interactive.dl-pill-clickable.dl-width-fit-content"))
                )
                driver.execute_script("arguments[0].click();", filter_button)
                time.sleep(2)
                
                # Handle video filter
                if filters.get('video', False):
                    try:
                        video_filter = wait.until(
                            EC.presence_of_element_located((By.XPATH,
                                "//span[contains(text(), 'Consultation vidéo disponible')]"))
                        )
                        driver.execute_script("arguments[0].click();", video_filter)
                        time.sleep(2)

                        # Cliquer sur le bouton "Afficher les résultats"
                        show_results_button = wait.until(
                            EC.presence_of_element_located((By.XPATH,
                                "//button[contains(text(), 'Afficher les résultats')]"))
                        )
                        driver.execute_script("arguments[0].click();", show_results_button)
                        time.sleep(3)  # Attendre le chargement des résultats
                    except Exception as e:
                        logger.error(f"Error with video filter: {e}")
                
                # Handle sector filter
                if 'sector' in filters:
                    try:
                        sector_mapping = {
                            "1": "//span[contains(text(), 'Secteur 1')]",
                            "2": "//span[contains(text(), 'Secteur 2')]",
                            "0": "//span[contains(text(), 'Non conventionné')]"
                        }
                        if filters['sector'] in sector_mapping:
                            sector_filter = wait.until(
                                EC.presence_of_element_located((By.XPATH,
                                    sector_mapping[filters['sector']]))
                            )
                            driver.execute_script("arguments[0].click();", sector_filter)
                            time.sleep(2)
                    except Exception as e:
                        logger.error(f"Error with sector filter: {e}")
                
                # Click confirm button
                try:
                    confirm_button = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR,
                            "button.Tappable-inactive.dl-button-primary.dl-button.dl-button-size-medium"))
                    )
                    driver.execute_script("arguments[0].click();", confirm_button)
                    time.sleep(3)
                except Exception as e:
                    logger.error(f"Error confirming filters: {e}")
                    
            except Exception as e:
                logger.error(f"Error in filter section: {e}")
                
    except Exception as e:
        logger.error(f"Error in search: {e}")

def extract_doctor_info(doctor_element):
    try:
        name = doctor_element.find_element(By.CSS_SELECTOR, 
            "h2.dl-text.dl-text-body.dl-text-bold.dl-text-s.dl-text-primary-110").text
        address = doctor_element.find_element(By.CSS_SELECTOR, ".dl-text").text
        sector = doctor_element.find_element(By.CSS_SELECTOR, 
            "p.XZWvFVZmM9FHf461kjNO.G5dSlmEET4Zf5bQ5PR69.p8ZDI8v1UHoMdXI35XEt").text
        availability = doctor_element.find_element(By.CSS_SELECTOR, 
            ".dl-search-result-availability").text
        
        return {
            'name': name,
            'address': address,
            'sector': sector,
            'availability': availability
        }
    except Exception as e:
        logger.error(f"Error extracting doctor info: {e}")
        return None

def save_to_csv(doctors, filename="doctors.csv"):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'address', 'sector', 'availability'])
        writer.writeheader()
        for doctor in doctors:
            if doctor:
                writer.writerow(doctor)

def main():
    speciality, location, filters = get_user_input()
    driver, wait = setup_driver()
    
    try:
        handle_cookies(wait)
        search_doctors(driver, wait, speciality, location, filters)
        
        # Wait for results to load
        time.sleep(3)
        
        # Get doctor cards
        doctor_cards = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".dl-search-result")
        ))
        
        # Extract information
        doctors = []
        logger.info("\n=== Médecins trouvés ===")
        
        for card in doctor_cards:
            doctor_info = extract_doctor_info(card)
            if doctor_info:
                doctors.append(doctor_info)
                logger.info("-" * 50)
                logger.info(f"Nom: {doctor_info['name']}")
                logger.info(f"Secteur: {doctor_info['sector']}")
                logger.info(f"Disponibilité: {doctor_info['availability']}")
                logger.info(f"Adresse: {doctor_info['address']}")
        
        logger.info("=" * 50)
        
        # Save results
        save_to_csv(doctors)
        logger.info(f"\nSauvegardé {len(doctors)} résultats dans doctors.csv")
        
    except Exception as e:
        logger.error(f"Une erreur est survenue: {str(e)}")
    
    finally:
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()