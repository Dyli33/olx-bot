# filepath: /Users/dyli/Documents/GitHub/olx-bot/olx-monitor-new.py
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
import random  # Add this import for random wait times

class OLXiPhoneScraper:
    def __init__(self):
        # Search filters configuration - easily editable
        self.search_filters = {
            'base_url': 'https://www.olx.pl/elektronika/telefony/warszawa/',
            'query': 'iphone',
            'distance': 30,  # km radius
            'order': 'created_at:desc',  # newest first
            'condition': ['used', 'damaged', 'new'],  # used new and damaged items
            'phone_models': [
                'iphone-11',
                'iphone-11-pro', 
                'iphone-11-pro-max',
                'iphone-12',
                'iphone-12-pro',
                'iphone-12-pro-max',
                'iphone-13',
                'iphone-13-pro',
                'iphone-13-pro-max',
                'iphone-14',
                'iphone-14-plus',
                'iphone-14-pro',
                'iphone-14-pro-max',
                'iphone-15',
                'iphone-15-pro',
                'iphone-15-pro-max'
            ]
        }
        
        # Price thresholds in PLN - easily editable
        self.price_limits = {
            "iPhone 11": 1370,
            "iPhone 11 Pro": 1470,
            "iPhone 11 Pro Max": 1570,
            "iPhone 12": 1520,
            "iPhone 12 Pro": 1820,
            "iPhone 12 Pro Max": 1920,
            "iPhone 13": 1920,
            "iPhone 13 Pro": 11300,
            "iPhone 13 Pro Max": 11450,
            "iPhone 14": 11250,
            "iPhone 14 Plus": 11350,
            "iPhone 14 Pro": 11850,
            "iPhone 14 Pro Max": 12050,
            "iPhone 15": 11950,
            "iPhone 15 Pro": 12550,
            "iPhone 15 Pro Max": 13050
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Add a list of user agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        ]
        
        # Track seen listings by URL to avoid duplicates
        self.seen_listings = set()
        
        # Control output verbosity
        self.verbose = True  # Set to False for less debug output
        
        # Load configuration for Telegram
        self.load_config()
        
        # Track listings that have been notified to prevent duplicate messages
        self.notified_listings = set()
        
        # Load previously notified listings from file to persist across restarts
        if hasattr(self, 'telegram_enabled') and self.telegram_enabled:
            self.load_notified_listings()

    def build_search_url(self):
        """Build the search URL dynamically based on filters"""
        base_url = self.search_filters['base_url']
        query = self.search_filters['query']
        
        # Start building the URL
        url = f"{base_url}q-{query}/"
        
        # Build query parameters
        params = {}
        
        # Distance filter
        if self.search_filters.get('distance'):
            params['search[dist]'] = str(self.search_filters['distance'])
        
        # Order filter
        if self.search_filters.get('order'):
            params['search[order]'] = self.search_filters['order']
        
        # Condition filter (used/new)
        if self.search_filters.get('condition'):
            params['search[filter_enum_state][0]'] = self.search_filters['condition']
        
        # Phone model filters
        if self.search_filters.get('phone_models'):
            for i, model in enumerate(self.search_filters['phone_models']):
                params[f'search[filter_enum_phonemodel][{i}]'] = model
        
        # Build the final URL with parameters
        if params:
            url += '?' + urllib.parse.urlencode(params, doseq=True)
        
        if self.verbose:
            print(f"Built search URL: {url}")
        
        return url

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
            if self.verbose:
                print(f"Could not parse price: {price_text}")
            return None

    def identify_phone_model(self, title):
        """Identify iPhone model from title - improved pattern matching"""
        title_lower = title.lower()
        
        # Define models in order of specificity (most specific first)
        model_patterns = [
            # iPhone 15 series
            (r'(iphone\s*15\s*pro\s*max|ip\s*15\s*pro\s*max|15\s*pro\s*max)', "iPhone 15 Pro Max"),
            (r'(iphone\s*15\s*pro|ip\s*15\s*pro|15\s*pro)(?!\s*max)', "iPhone 15 Pro"),
            (r'(iphone\s*15|ip\s*15|15)(?!\s*pro)', "iPhone 15"),
            
            # iPhone 14 series
            (r'(iphone\s*14\s*pro\s*max|ip\s*14\s*pro\s*max|14\s*pro\s*max)', "iPhone 14 Pro Max"),
            (r'(iphone\s*14\s*plus|ip\s*14\s*plus|14\s*plus)', "iPhone 14 Plus"),
            (r'(iphone\s*14\s*pro|ip\s*14\s*pro|14\s*pro)(?!\s*max)', "iPhone 14 Pro"),
            (r'(iphone\s*14|ip\s*14|14)(?!\s*pro|\s*plus)', "iPhone 14"),
            
            # iPhone 13 series
            (r'(iphone\s*13\s*pro\s*max|ip\s*13\s*pro\s*max|13\s*pro\s*max)', "iPhone 13 Pro Max"),
            (r'(iphone\s*13\s*pro|ip\s*13\s*pro|13\s*pro)(?!\s*max)', "iPhone 13 Pro"),
            (r'(iphone\s*13|ip\s*13|13)(?!\s*pro)', "iPhone 13"),
            
            # iPhone 12 series
            (r'(iphone\s*12\s*pro\s*max|ip\s*12\s*pro\s*max|12\s*pro\s*max)', "iPhone 12 Pro Max"),
            (r'(iphone\s*12\s*pro|ip\s*12\s*pro|12\s*pro)(?!\s*max)', "iPhone 12 Pro"),
            (r'(iphone\s*12|ip\s*12|12)(?!\s*pro)', "iPhone 12"),
            
            # iPhone 11 series
            (r'(iphone\s*11\s*pro\s*max|ip\s*11\s*pro\s*max|11\s*pro\s*max)', "iPhone 11 Pro Max"),
            (r'(iphone\s*11\s*pro|ip\s*11\s*pro|11\s*pro)(?!\s*max)', "iPhone 11 Pro"),
            (r'(iphone\s*11|ip\s*11|11)(?!\s*pro)', "iPhone 11"),
        ]
        
        # Try each pattern
        for pattern, model_name in model_patterns:
            if re.search(pattern, title_lower):
                if self.verbose:
                    print(f"Matched '{title}' to {model_name}")
                return model_name
        
        if self.verbose:
            print(f"Could not identify model from title: {title}")
        return None

    def extract_description(self, listing_url):
        """Extract detailed description from listing page"""
        try:
            if self.verbose:
                print(f"Fetching description from: {listing_url}")
            
            response = requests.get(listing_url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return "No description available"
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try different selectors for OLX description
            description_selectors = [
                {'data-cy': 'ad_description'},
                {'class': re.compile(r'.*description.*', re.I)},
                {'id': 'textContent'}
            ]
            
            for selector in description_selectors:
                desc_elem = soup.find('div', selector)
                if desc_elem:
                    # Clean up the description
                    for script in desc_elem.find_all(['script', 'style']):
                        script.decompose()
                    
                    description = desc_elem.get_text(separator=' ', strip=True)
                    
                    # Clean up unwanted content
                    description = re.sub(r'(font-size|line-height|margin|padding|color|text-transform):[^;]*;?', '', description)
                    description = re.sub(r'\.css-[a-zA-Z0-9_-]+', '', description)
                    description = re.sub(r'\{[^}]*\}', '', description)
                    description = re.sub(r'\s+', ' ', description).strip()
                    
                    if len(description) > 20 and not re.search(r'(css-|font-size)', description):
                        return description[:300] + ('...' if len(description) > 300 else '')
            
            return "No description available"
            
        except Exception as e:
            if self.verbose:
                print(f"Error extracting description: {e}")
            return "No description available"

    def scrape_listings(self):
        """Scrape iPhone listings from OLX using dynamic URL"""
        print("Starting to scrape iPhone listings from OLX...")
        
        # Build the search URL dynamically
        search_url = self.build_search_url()
        
        try:
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find listing containers with multiple selectors
            listing_selectors = [
                {'data-cy': 'l-card'},
                {'class': re.compile(r'offer-wrapper', re.I)},
                {'class': re.compile(r'.*listing.*', re.I)}
            ]
            
            listings = []
            for selector in listing_selectors:
                found = soup.find_all('div', selector)
                if found:
                    listings = found
                    break
            
            if not listings:
                print("No listings found. The page structure might have changed.")
                if self.verbose:
                    print("Page content preview:")
                    print(soup.get_text()[:500])
                return []
            
            print(f"Found {len(listings)} potential listings")
            
            valid_listings = []
            skipped_count = 0
            skipped_models = {}
            
            for i, listing in enumerate(listings):
                try:
                    # Extract title with multiple selectors
                    title_selectors = [
                        {'data-cy': 'listing-ad-title'},
                        'h6', 'h4', 'h5'
                    ]
                    
                    title_elem = None
                    for selector in title_selectors:
                        if isinstance(selector, dict):
                            title_elem = listing.find('a', selector) or listing.find('h6', selector)
                        else:
                            title_elem = listing.find(selector)
                        if title_elem:
                            break
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Extract price with multiple selectors
                    price_selectors = [
                        {'data-testid': 'ad-price'},
                        {'class': re.compile(r'.*price.*', re.I)}
                    ]
                    
                    price_elem = None
                    for selector in price_selectors:
                        price_elem = listing.find('p', selector) or listing.find('span', selector)
                        if price_elem:
                            break
                    
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
                    
                    # Skip if already seen
                    if link in self.seen_listings:
                        continue
                    
                    # Identify phone model
                    phone_model = self.identify_phone_model(title)
                    if not phone_model:
                        continue
                    
                    # Check price limit
                    if phone_model in self.price_limits:
                        max_price = self.price_limits[phone_model]
                        if price > max_price:
                            if self.verbose:
                                print(f"SKIPPED: {phone_model} at {price} zł > {max_price} zł limit")
                            
                            skipped_models[phone_model] = skipped_models.get(phone_model, 0) + 1
                            skipped_count += 1
                            continue
                    else:
                        if self.verbose:
                            print(f"WARNING: No price limit defined for {phone_model}")
                        continue
                    
                    # Extract description (optional, can be slow)
                    description = self.extract_description(link)
                    
                    listing_data = {
                        'phone_name': phone_model,
                        'price': price,
                        'description': description,
                        'link': link,
                        'title': title
                    }
                    
                    # Add to seen listings
                    self.seen_listings.add(link)
                    valid_listings.append(listing_data)
                    
                    print(f"✓ Found: {phone_model} - {price} zł")
                    
                    # Send notification if new
                    if hasattr(self, 'telegram_enabled') and self.telegram_enabled and link not in self.notified_listings:
                        self.send_telegram_notification(listing_data)
                        self.notified_listings.add(link)
                        self.save_notified_listings()
                    
                    # Limit processing
                    if len(valid_listings) >= 20:
                        print("Reached maximum listings limit (20)")
                        break
                    
            
                    
                except Exception as e:
                    if self.verbose:
                        print(f"Error processing listing {i+1}: {e}")
                    continue
            
            # Print summary
            if skipped_count > 0:
                print(f"\nSkipped {skipped_count} listings due to price limits:")
                for model, count in skipped_models.items():
                    print(f"  - {model}: {count} listings")
            
            print(f"Found {len(valid_listings)} valid listings within price limits")
            return valid_listings
            
        except requests.RequestException as e:
            print(f"Network error: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error: {e}")
            if self.verbose:
                import traceback
                print(traceback.format_exc())
            return []

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
                print("Telegram notifications disabled")
            
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
            message = f"🍎 *New iPhone Deal Found!*\n\n"
            message += f"📱 *Model:* {listing['phone_name']}\n"
            message += f"💰 *Price:* {listing['price']} zł\n"
            
            if (self.include_description and 
                listing['description'] and 
                listing['description'] != "No description available"):
                desc = listing['description']
                if len(desc) > 200:
                    desc = desc[:200] + "..."
                message += f"📝 *Description:* {desc}\n"
            
            message += f"🔗 [View Listing]({listing['link']})"
            
            # Ensure message isn't too long
            if len(message) > self.max_message_length:
                message = message[:self.max_message_length-10] + "..."
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            
            print(f"📱 Telegram notification sent for {listing['phone_name']}")
            return True
            
        except Exception as e:
            print(f"Telegram error: {e}")
            return False

    def send_telegram_notification(self, listing):
        """Wrapper to run async Telegram sending"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.send_telegram_message(listing))
            loop.close()
            return result
        except Exception as e:
            print(f"Error in Telegram notification wrapper: {e}")
            return False

    def run(self):
        """Main method to run the scraper"""
        try:
            print("OLX iPhone Scraper Started")
            print("-" * 40)
            print(f"Searching for: {', '.join(self.search_filters['phone_models'])}")
            print(f"Max distance: {self.search_filters['distance']} km")
            print(f"Condition: {self.search_filters['condition']}")
            print("-" * 40)
            
            listings = self.scrape_listings()
            
            if listings:
                print(f"\n✅ Found {len(listings)} valid listings matching criteria")
                for listing in listings[:5]:  # Show first 5
                    print(f"  • {listing['phone_name']} - {listing['price']} zł")
                if len(listings) > 5:
                    print(f"  • ... and {len(listings) - 5} more")
            else:
                print("❌ No valid listings found matching price criteria")
            
        except Exception as e:
            print(f"ERROR in run method: {e}")
            if self.verbose:
                import traceback
                print(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    try:
        scraper = OLXiPhoneScraper()
        
        print("🔍 Starting OLX iPhone monitoring...")
        print("Press Ctrl+C to stop.")
        print("=" * 50)
        
        cycle = 1
        while True:
            try:
                print(f"\nCycle #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 30)
                
                scraper.run()
                
                wait_time = random.uniform(3, 5)  # Random wait between 3-5 seconds
                print(f"\nCycle #{cycle} completed. Waiting {wait_time:.1f} seconds...")
                print("=" * 50)

                cycle += 1
                time.sleep(wait_time)  # Wait for the random interval
                
            except requests.exceptions.RequestException as e:
                print(f"\n🌐 Network error in cycle #{cycle}: {e}")
                print("Retrying in 60 seconds...")
                time.sleep(60)
                continue
            except Exception as e:
                print(f"\n⚠️ Error in cycle #{cycle}: {e}")
                print("Continuing in 60 seconds...")
                time.sleep(60)
                continue
            
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped by user.")
    except Exception as e:
        print(f"\n💥 Critical error: {e}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
    finally:
        print("\n🏁 Program terminated.")
