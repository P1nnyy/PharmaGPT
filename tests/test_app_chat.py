import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from streamlit.testing.v1 import AppTest

# Mock the dependencies before they are imported by app.py
# We need to mock 'shop_manager' and 'agent'
sys.modules["shop_manager"] = MagicMock()
sys.modules["agent"] = MagicMock()

# Setup the mocks
mock_shop = MagicMock()
sys.modules["shop_manager"].PharmaShop.return_value = mock_shop
mock_shop.get_product_names.return_value = ["Dolo 650", "Augmentin"]
mock_shop.check_inventory.return_value = []

# Mock run_agent
mock_run_agent = MagicMock(return_value="I am a mocked agent response.")
sys.modules["agent"].run_agent = mock_run_agent

class TestAppChat(unittest.TestCase):
    def setUp(self):
        # Set env var to avoid warning
        os.environ["GOOGLE_API_KEY"] = "fake_key"

    def test_chat_interaction(self):
        """
        Test that entering a message in the chat input adds it to session state
        and displays the agent response.
        """
        # Initialize the app
        at = AppTest.from_file("app.py")
        
        # Run the app
        at.run()
        
        # Check initial state
        # Tab 1 is index 0
        # We need to find the chat_input. It might be nested.
        # The app has tabs. chat_input is in tab1.
        
        # Simulate user input
        # Note: In AppTest, we interact with elements.
        # We need to find the chat_input.
        
        # Check if chat_input exists
        self.assertTrue(at.chat_input, "Chat input not found")
        
        # Enter text
        at.chat_input[0].set_value("Hello Agent").run()
        
        # Check if the message is displayed
        # We expect 2 chat_messages: one user, one assistant (plus any history if persisted, but this is a fresh run)
        # Actually, app.py initializes messages = [] if not present.
        
        # The app renders chat_message elements.
        # We can check markdown elements inside chat_message.
        
        # at.chat_message should give us the chat message containers.
        chat_messages = at.chat_message
        self.assertEqual(len(chat_messages), 2, "Expected 2 chat messages (User + Assistant)")
        
        # Check content
        # The first one is User
        self.assertEqual(chat_messages[0].markdown[0].value, "Hello Agent")
        
        # The second one is Assistant
        self.assertEqual(chat_messages[1].markdown[0].value, "I am a mocked agent response.")
        
        # Verify run_agent was called
        # Note: Since AppTest re-imports/runs the script, the mock might be tricky if it reloads modules.
        # But since we patched sys.modules, it should use our mocks.
        # Let's verify.
        # Actually, AppTest might run in a way that reloads.
        # But if it works, the output check confirms it.

if __name__ == "__main__":
    unittest.main()
