import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
import urllib.parse
import json
import os
from telegram import Bot
from telegram.error import TelegramError
import asyncio

class OLXiPhoneScraper:
    def __init__(self):
        self.url = "https://www.olx.pl/elektronika/telefony/warszawa/q-iphone/?search%5Bdist%5D=30&search%5Border%5D=created_at:desc&search%5Bfilter_enum_state%5D%5B0%5D=used&search%5Bfilter_enum_phonemodel%5D%5B0%5D=iphone-15&search%5Bfilter_enum_phonemodel%5D%5B1%5D=iphone-14-pro&search%5Bfilter_enum_phonemodel%5D%5B2%5D=iphone-15-pro-max&search%5Bfilter_enum_phonemodel%5D%5B3%5D=iphone-13&search%5Bfilter_enum_phonemodel%5D%5B4%5D=iphone-13-pro&search%5Bfilter_enum_phonemodel%5D%5B5%5D=iphone-12-pro-max&search%5Bfilter_enum_phonemodel%5D%5B6%5D=iphone-13-pro-max&search%5Bfilter_enum_phonemodel%5D%5B7%5D=iphone-12&search%5Bfilter_enum_phonemodel%5D%5B8%5D=iphone-11-pro-max&search%5Bfilter_enum_phonemodel%5D%5B9%5D=iphone-11&search%5Bfilter_enum_phonemodel%5D%5B10%5D=iphone-12-pro&search%5Bfilter_enum_phonemodel%5D%5B11%5D=iphone-11-pro&search%5Bfilter_enum_phonemodel%5D%5B12%5D=iphone-14-pro-max&search%5Bfilter_enum_phonemodel%5D%5B13%5D=iphone-14&search%5Bfilter_enum_phonemodel%5D%5B14%5D=iphone-15-pro"
        
        # Price thresholds in PLN
        self.price_limits = {
            "iPhone 11": 400,
            "iPhone 11 Pro": 500,
            "iPhone 11 Pro Max": 600,
            "iPhone 12": 550,
            "iPhone 12 Pro": 850,
            "iPhone 12 Pro Max": 950,
            "iPhone 13": 950,
            "iPhone 13 Pro": 1350,
            "iPhone 13 Pro Max": 1450,
            "iPhone 14": 1250,
            "iPhone 14 Plus": 1300,
            "iPhone 14 Pro": 1850,
            "iPhone 14 Pro Max": 2050,
            "iPhone 15": 1950,
            "iPhone 15 Pro": 2550,
            "iPhone 15 Pro Max": 3050
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Track seen listings by URL to avoid duplicates
        self.seen_listings = set()
        
        # Control output verbosity
        self.verbose = False  # Set to True for detailed debug output
        
        # Load configuration for Telegram
        self.load_config()
        
        # Track listings that have been notified to prevent duplicate messages
        self.notified_listings = set()
        
        # Load previously notified listings from file to persist across restarts
        if self.telegram_enabled:
            self.load_notified_listings()

    def extract_price(self, price_text):
        """Extract numeric price from text"""
        if not price_text:
            return None
        
        # Remove all non-numeric characters except dots and commas
        price_clean = re.sub(r'[^\d,.]', '', price_text.strip())
        
        # Handle different number formats
        if ',' in price_clean and '.' in price_clean:
            # Format like 1,234.56
            price_clean = price_clean.replace(',', '')
        elif ',' in price_clean:
            # Format like 1234,56 (Polish format)
            price_clean = price_clean.replace(',', '.')
        
        try:
            return float(price_clean)
        except ValueError:
            return None

    def identify_phone_model(self, title):
        """Identify iPhone model from title - case insensitive"""
        title_lower = title.lower()
        
        # Base patterns to look for (without caring about case)
        base_patterns = [
            "iphone 15 pro max",
            "iphone 15 pro",
            "iphone 15",
            "iphone 14 pro max", 
            "iphone 14 plus",
            "iphone 14 pro",
            "iphone 14",
            "iphone 13 pro max",
            "iphone 13 pro",
            "iphone 13",
            "iphone 12 pro max",
            "iphone 12 pro",
            "iphone 12",
            "iphone 11 pro max",
            "iphone 11 pro",
            "iphone 11"
        ]
        
        # Map any variation to the standard format used in price_limits dictionary
        model_mapping = {
            "iphone 15 pro max": "iPhone 15 Pro Max",
            "iphone 15 pro": "iPhone 15 Pro",
            "iphone 15": "iPhone 15",
            "iphone 14 pro max": "iPhone 14 Pro Max",
            "iphone 14 plus": "iPhone 14 Plus",
            "iphone 14 pro": "iPhone 14 Pro",
            "iphone 14": "iPhone 14",
            "iphone 13 pro max": "iPhone 13 Pro Max",
            "iphone 13 pro": "iPhone 13 Pro",
            "iphone 13": "iPhone 13",
            "iphone 12 pro max": "iPhone 12 Pro Max",
            "iphone 12 pro": "iPhone 12 Pro",
            "iphone 12": "iPhone 12",
            "iphone 11 pro max": "iPhone 11 Pro Max",
            "iphone 11 pro": "iPhone 11 Pro",
            "iphone 11": "iPhone 11"
        }
        
        # Additional common variations to handle
        variation_mapping = {
            # Handle with/without space after "iPhone"
            "iphone15 pro max": "iphone 15 pro max",
            "iphone15 pro": "iphone 15 pro", 
            "iphone15": "iphone 15",
            "iphone14 pro max": "iphone 14 pro max",
            "iphone14 plus": "iphone 14 plus",
            "iphone14 pro": "iphone 14 pro",
            "iphone14": "iphone 14",
            "iphone13 pro max": "iphone 13 pro max",
            "iphone13 pro": "iphone 13 pro",
            "iphone13": "iphone 13",
            "iphone12 pro max": "iphone 12 pro max",
            "iphone12 pro": "iphone 12 pro",
            "iphone12": "iphone 12",
            "iphone11 pro max": "iphone 11 pro max",
            "iphone11 pro": "iphone 11 pro",
            "iphone11": "iphone 11",
            
            # Handle different spacings/formats
            "ip 15 pro max": "iphone 15 pro max",
            "ip 15 pro": "iphone 15 pro",
            "ip 15": "iphone 15",
            "ip15promax": "iphone 15 pro max",
            "ip15pro": "iphone 15 pro",
            "ip15": "iphone 15",
            
            # Handle common typos/abbreviations
            "iph 15 pro max": "iphone 15 pro max",
            "iph 15 pro": "iphone 15 pro",
            "iph 15": "iphone 15",
            
            # Handle different capitalizations
            "IPHONE 15": "iphone 15",
            "IPHONE 15 PRO": "iphone 15 pro",
            "IPHONE 15 PRO MAX": "iphone 15 pro max",
            "Iphone 15": "iphone 15",
            "Iphone 15 Pro": "iphone 15 pro",
            "Iphone 15 Pro Max": "iphone 15 pro max",
            
            "IPHONE 14": "iphone 14",
            "IPHONE 14 PRO": "iphone 14 pro",
            "IPHONE 14 PRO MAX": "iphone 14 pro max",
            "IPHONE 14 PLUS": "iphone 14 plus",
            "Iphone 14": "iphone 14",
            "Iphone 14 Pro": "iphone 14 pro",
            "Iphone 14 Pro Max": "iphone 14 pro max",
            "Iphone 14 Plus": "iphone 14 plus",
            
            "IPHONE 13": "iphone 13",
            "IPHONE 13 PRO": "iphone 13 pro",
            "IPHONE 13 PRO MAX": "iphone 13 pro max",
            "Iphone 13": "iphone 13",
            "Iphone 13 Pro": "iphone 13 pro",
            "Iphone 13 Pro Max": "iphone 13 pro max",
            
            "IPHONE 12": "iphone 12",
            "IPHONE 12 PRO": "iphone 12 pro",
            "IPHONE 12 PRO MAX": "iphone 12 pro max",
            "Iphone 12": "iphone 12",
            "Iphone 12 Pro": "iphone 12 pro",
            "Iphone 12 Pro Max": "iphone 12 pro max",
            
            "IPHONE 11": "iphone 11",
            "IPHONE 11 PRO": "iphone 11 pro",
            "IPHONE 11 PRO MAX": "iphone 11 pro max",
            "Iphone 11": "iphone 11",
            "Iphone 11 Pro": "iphone 11 pro",
            "Iphone 11 Pro Max": "iphone 11 pro max",
        }
        
        # First try direct matching with standard patterns - case insensitive
        for model in base_patterns:
            if model in title_lower or model.upper() in title.upper():
                return model_mapping[model]
        
        # Then try with variation mapping for common alternate formats
        for variation, standard in variation_mapping.items():
            if variation in title_lower:
                return model_mapping[standard]
        
        # If no exact match, try a more aggressive approach for partial matches
        for model in base_patterns:
            # Create parts - e.g. ['iphone', '14', 'pro', 'max']
            parts = model.split()
            if len(parts) < 2:  # Need at least iPhone + model number
                continue
                
            # Check if both iphone and model number are in the title
            if parts[0] in title_lower and parts[1] in title_lower:
                # For models with additional descriptors (pro, max)
                if len(parts) > 2:
                    # Check if the descriptor is also present
                    if parts[2] in title_lower:
                        if len(parts) > 3 and parts[3] in title_lower:  # For "pro max"
                            return model_mapping[model]
                        elif len(parts) == 3:  # Just "pro" or "plus"
                            return model_mapping[model]
                else:
                    # Basic model (iPhone X)
                    return model_mapping[model]
        
        return None

    def scrape_listings(self):
        """Scrape iPhone listings from OLX"""
        print("Starting to scrape iPhone listings from OLX...")
        
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find listing containers - OLX uses different selectors
            listings = soup.find_all('div', {'data-cy': 'l-card'}) or \
                      soup.find_all('div', class_=re.compile(r'offer-wrapper')) or \
                      soup.find_all('div', class_=re.compile(r'css-.*'))
            
            if not listings:
                print("No listings found. The page structure might have changed.")
                return []
            
            print(f"Found {len(listings)} potential listings")
            
            valid_listings = []
            skipped_count = 0
            skipped_models = {}  # Track skipped models and their count
            
            for i, listing in enumerate(listings):  # Check all listings
                try:
                    # Extract title
                    title_elem = listing.find('h6') or listing.find('h4') or listing.find('a', {'data-cy': 'listing-ad-title'})
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Extract price
                    price_elem = listing.find('p', {'data-testid': 'ad-price'}) or \
                                listing.find('span', class_=re.compile(r'price')) or \
                                listing.find('p', string=re.compile(r'zł'))
                    
                    if not price_elem:
                        continue
                    
                    price_text = price_elem.get_text(strip=True)
                    price = self.extract_price(price_text)
                    
                    if price is None:
                        continue
                    
                    # Extract link
                    link_elem = listing.find('a', href=True)
                    if not link_elem:
                        continue
                    
                    link = link_elem['href']
                    if link.startswith('/'):
                        link = 'https://www.olx.pl' + link
                    
                    # Identify phone model
                    phone_model = self.identify_phone_model(title)
                    if not phone_model:
                        continue
                    
                    # Check if price is within limit
                    if phone_model in self.price_limits:
                        max_price = self.price_limits[phone_model]
                        if price > max_price:
                            if self.verbose:
                                print(f"PRICE EXCEEDS LIMIT: {phone_model} at {price} zł > {max_price} zł")
                            
                            # Keep track of skipped models
                            if phone_model in skipped_models:
                                skipped_models[phone_model] += 1
                            else:
                                skipped_models[phone_model] = 1
                                
                            skipped_count += 1
                            continue
                    else:
                        # This should never happen with our new mapping
                        if self.verbose:
                            print(f"WARNING: No price limit for {phone_model}")
                        continue
                    
                    # Skip extracting description from listing preview - it's often just the price
                    # Always fetch the full listing page for proper description
                    description = "No description available"
                    
                    try:
                        print(f"Fetching full page for detailed description: {link}")
                        detail_page = requests.get(link, headers=self.headers, timeout=10)
                        if detail_page.status_code == 200:
                            detail_soup = BeautifulSoup(detail_page.content, 'html.parser')
                            
                            # Try different selectors for OLX descriptions
                            # Main OLX description container
                            detail_desc = detail_soup.find('div', {'data-cy': 'ad_description'})
                            
                            # Fallback to other common selectors for description
                            if not detail_desc or not detail_desc.text.strip():
                                detail_desc = detail_soup.find('div', class_=re.compile(r'css-.*description')) or \
                                            detail_soup.find('div', class_='descriptioncontent') or \
                                            detail_soup.find('div', id='textContent')
                                
                            # Parse out any specific description content
                            if detail_desc:
                                # Remove all style and script tags to avoid CSS content
                                for script in detail_desc.find_all(['script', 'style']):
                                    script.decompose()
                                
                                # Get clean text content without CSS
                                description_text = detail_desc.get_text(separator=' ', strip=True)
                                
                                # Filter out CSS-like content and other unwanted text
                                # Remove CSS rules (anything containing { } or starting with .)
                                description_text = re.sub(r'\.[a-zA-Z0-9_-]+\{[^}]*\}', '', description_text)
                                description_text = re.sub(r'\.css-[a-zA-Z0-9_-]+\{[^}]*\}', '', description_text)
                                description_text = re.sub(r'\{[^}]*\}', '', description_text)
                                
                                # Remove common CSS properties and values
                                description_text = re.sub(r'(font-size|line-height|margin|padding|color|text-transform|font-family):[^;]*;?', '', description_text)
                                
                                # Remove standalone CSS class names
                                description_text = re.sub(r'\.css-[a-zA-Z0-9_-]+', '', description_text)
                                
                                # Clean up common prefixes and formatting issues
                                description_text = re.sub(r'^(Opis:?\s*|Description:?\s*|O przedmiocie:?\s*)', '', description_text)
                                description_text = re.sub(r'\s+', ' ', description_text)  # Normalize whitespace
                                description_text = description_text.strip()
                                
                                # Skip if description is just the price again or contains CSS
                                if (len(description_text) > 15 and 
                                    not re.match(r'^[\d\s,.]+\s?zł$', description_text) and
                                    not re.search(r'\.css-|font-size|line-height|\{|\}', description_text)):
                                    description = description_text
                                    print(f"Found detailed description ({len(description)} chars): {description[:50]}...")
                                else:
                                    print(f"Found description but it appears to be CSS/price: '{description_text[:100]}...'")
                            
                    except Exception as detail_err:
                        print(f"Error fetching detailed description: {str(detail_err)}")
                    
                    listing_data = {
                        'phone_name': phone_model,
                        'price': price,
                        'description': description[:300] + '...' if len(description) > 300 else description,
                        'link': link,
                        'title': title
                    }
                    
                    # Add to seen listings
                    self.seen_listings.add(link)
                    
                    valid_listings.append(listing_data)
                    print(f"Found valid listing: {phone_model} - {price} zł ✓")
                    
                    # Send Telegram notification for the new listing
                    if link not in self.notified_listings:
                        # Attempt to send notification
                        try:
                            print(f"📱 Sending Telegram notification for NEW listing: {phone_model}")
                            self.send_telegram_notification(listing_data)
                            # Mark this listing as notified
                            self.notified_listings.add(link)
                            # Save updated notification list
                            self.save_notified_listings()
                        except Exception as e:
                            print(f"Failed to send Telegram notification for {phone_model}: {e}")
                    else:
                        print(f"⏭️  Skipping notification for {phone_model} - already notified before")
                    
                    # Stop if we've found enough listings
                    if len(valid_listings) >= 20:
                        print("Reached maximum number of listings to process.")
                        break
                    
                except Exception as e:
                    print(f"Error processing listing {i+1}: {str(e)}")
                    continue
            
            # Print summary of skipped listings by model
            if skipped_count > 0:
                print(f"\nSkipped listings summary (due to price limits):")
                for model, count in skipped_models.items():
                    print(f"  - {model}: {count} listings")
                    
            print(f"Total: {len(valid_listings)} valid listings, {skipped_count} skipped due to price limits")
            
            # Debug output to ensure we're returning listings correctly
            if valid_listings:
                print(f"Debug: Found {len(valid_listings)} valid listings to save")
                for listing in valid_listings[:2]:  # Show first two as sample
                    print(f"  - {listing['phone_name']} at {listing['price']} zł")
                if len(valid_listings) > 2:
                    print(f"  - ... and {len(valid_listings) - 2} more")
            
            return valid_listings
            
        except requests.RequestException as e:
            print(f"Error fetching page: {str(e)}")
            return []
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []

    def run(self):
        """Main method to run the scraper"""
        try:
            print("OLX iPhone Scraper Started")
            print("-" * 30)
            
            listings = self.scrape_listings()
            
            if listings:
                # Listings are already filtered during scraping
                print(f"\nFound {len(listings)} valid listings matching criteria and price limits")
            else:
                print("No valid listings found matching price criteria")
                
        except Exception as e:
            print(f"ERROR in run method: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                
            telegram_config = config.get('telegram', {})
            self.bot_token = telegram_config.get('bot_token')
            self.chat_id = telegram_config.get('chat_id')
            self.telegram_enabled = telegram_config.get('enabled', False) and self.bot_token
            
            if self.telegram_enabled:
                self.bot = Bot(token=self.bot_token)
                print(f"Telegram notifications enabled for chat ID: {self.chat_id}")
            else:
                print("Telegram notifications disabled - check config.json")
                
            # Notification settings
            notification_settings = config.get('notification_settings', {})
            self.max_message_length = notification_settings.get('max_message_length', 4000)
            self.include_description = notification_settings.get('include_description', True)
            
        except FileNotFoundError:
            print("config.json not found - Telegram notifications disabled")
            self.telegram_enabled = False
        except Exception as e:
            print(f"Error loading config: {e}")
            self.telegram_enabled = False

    def load_notified_listings(self):
        """Load previously notified listings from file"""
        try:
            with open('notified_listings.txt', 'r') as f:
                self.notified_listings = set(line.strip() for line in f if line.strip())
            print(f"Loaded {len(self.notified_listings)} previously notified listings")
        except FileNotFoundError:
            print("No previous notification history found")
        except Exception as e:
            print(f"Error loading notification history: {e}")

    def save_notified_listings(self):
        """Save notified listings to file"""
        try:
            with open('notified_listings.txt', 'w') as f:
                for listing_url in self.notified_listings:
                    f.write(f"{listing_url}\n")
        except Exception as e:
            print(f"Error saving notification history: {e}")

    async def send_telegram_message(self, listing):
        """Send Telegram message for a new listing"""
        if not self.telegram_enabled:
            return False
            
        try:
            # Format the message
            message = f"🍎 *New iPhone Deal Found!*\n\n"
            message += f"📱 *Model:* {listing['phone_name']}\n"
            message += f"💰 *Price:* {listing['price']} zł\n"
            
            if self.include_description and listing['description'] and listing['description'] != "No description available":
                # Truncate description if too long
                desc = listing['description']
                if len(desc) > 200:
                    desc = desc[:200] + "..."
                message += f"📝 *Description:* {desc}\n"
            
            message += f"🔗 [View Listing]({listing['link']})"
            
            # Ensure message isn't too long
            if len(message) > self.max_message_length:
                message = message[:self.max_message_length-10] + "..."
            
            # Send the message
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            
            print(f"Telegram message sent successfully for {listing['phone_name']}")
            return True
            
        except TelegramError as e:
            print(f"Telegram error: {e}")
            return False
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False

    def send_telegram_notification(self, listing):
        """Wrapper to run async Telegram sending"""
        try:
            # Run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.send_telegram_message(listing))
            loop.close()
            return result
        except Exception as e:
            print(f"Error in Telegram notification wrapper: {e}")
            return False

if __name__ == "__main__":
    try:
        scraper = OLXiPhoneScraper()
        
        print("Starting OLX monitoring. Press Ctrl+C to stop.")
        print("=" * 50)
        
        # Display initial stats
        print(f"Unique listings tracked: {len(scraper.seen_listings)}")
        
        cycle = 1
        while True:
            try:
                print(f"\nCycle #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 30)
                
                scraper.run()
                
                print(f"Cycle #{cycle} completed. Waiting 30 seconds before next check...")
                print("=" * 50)
                
                cycle += 1
                time.sleep(30)  # Wait for 30 seconds before next scrape
            except requests.exceptions.RequestException as e:
                print(f"\nNETWORK ERROR in cycle #{cycle}: {str(e)}")
                print("Will retry in 30 seconds...")
                time.sleep(30)
                continue
            except Exception as e:
                print(f"\nERROR in cycle #{cycle}: {str(e)}")
                import traceback
                print(f"Detailed error: {traceback.format_exc()}")
                print("Continuing to next cycle in 30 seconds...")
                time.sleep(30)
                continue
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
    except Exception as e:
        import traceback
        print("\n\nCRITICAL ERROR: Program crashed")
        print(f"Error message: {str(e)}")
        print(f"Detailed traceback:\n{traceback.format_exc()}")
    finally:
        print("\nProgram terminated.")