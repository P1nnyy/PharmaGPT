from typing import TypedDict, Annotated, List, Union
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from shop_manager import PharmaShop
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# Initialize Shop
shop = PharmaShop()

# --- Tools ---

@tool
def check_inventory_tool():
    """
    Useful for checking what items are in stock, their batch numbers, and expiry dates.
    Returns a string summary of the inventory.
    """
    inventory = shop.check_inventory()
    if not inventory:
        return "The inventory is empty."
    
    # Format nicely
    summary = "Current Inventory:\n"
    for item in inventory:
        # item['Stock'] is the readable string like "5 Strips, 3 Loose"
        # We can extract pack size from the raw data if we want, but check_inventory returns it now?
        # Wait, check_inventory returns a list of dicts. Let's check what keys it has.
        # It has "Product", "Batch", "Stock", "Stock_Raw", "Expiry".
        # It does NOT explicitly return "Pack Size" in the dict, but we can infer or update check_inventory to return it.
        # Actually, let's just use the readable string which implies the pack structure.
        # But the agent might need the explicit number.
        # Let's update shop_manager.py's check_inventory to return 'Pack_Size' in the dict first?
        # Or just rely on the readable string.
        # "Stock": "5 Strips, 3 Loose" is good.
        summary += f"- {item['Product']} (Batch: {item['Batch']}): {item['Stock']}, Expires: {item['Expiry']}\n"
    return summary

@tool
def sell_item_tool(product_name: str, quantity: int):
    """
    Useful for processing a sale. Use this when the user wants to sell or buy a product.
    Requires product_name and quantity.
    """
    try:
        result = shop.sell_item(product_name, quantity)
        return f"Successfully sold {result['qty']} of {result['product']}. Tax collected: ${result['tax']:.2f}. Details: {result['details']}"
    except ValueError as e:
        # Check for fuzzy matches if product not found
        if "not found" in str(e).lower():
            suggestions = shop.find_product_fuzzy(product_name)
            if suggestions:
                return f"Error: {e}. Did you mean: {', '.join(suggestions)}?"
        return f"Error: {e}"
    except Exception as e:
        return f"System Error: {e}"

tools = [check_inventory_tool, sell_item_tool]

# --- Agent State ---

from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

# --- Nodes ---

def get_llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables.")
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key, temperature=0)

def supervisor_node(state: AgentState):
    messages = state['messages']
    try:
        llm = get_llm()
        llm_with_tools = llm.bind_tools(tools)
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Error: {str(e)}")]}

def should_continue(state: AgentState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "tools"
    return END

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    should_continue,
    {
        "tools": "tools",
        END: END
    }
)

workflow.add_edge("tools", "supervisor")

app = workflow.compile()

def run_agent(user_input: str):
    """
    Run the agent with a user input string.
    Returns the final response string.
    """
    # Merge system prompt into the first HumanMessage to avoid Gemini API issues with SystemMessage + Tools
    system_prompt = "You are a helpful pharmacy assistant. Use the available tools to manage inventory and sales."
    combined_input = f"{system_prompt}\n\nUser Request: {user_input}"
    
    initial_state = {"messages": [HumanMessage(content=combined_input)]}
    result = app.invoke(initial_state)
    return result['messages'][-1].content