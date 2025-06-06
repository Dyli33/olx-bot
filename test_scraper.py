# Test version of the OLX scraper - runs only one cycle
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, '/Users/dyli/Documents/GitHub/olx-bot')

# Import the scraper class
from olx_monitor_new import OLXiPhoneScraper

if __name__ == "__main__":
    try:
        print("🧪 Testing OLX iPhone Scraper...")
        print("=" * 50)
        
        # Create scraper instance
        scraper = OLXiPhoneScraper()
        
        # Run one test cycle
        scraper.run()
        
        print("\n🏁 Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
