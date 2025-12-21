#!/usr/bin/env python3
import os
import sys
import pandas as pd
import ccxt
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

try:
    from exchanges.paper import Paper
except ImportError:
    print("Warning: Paper module not found in exchanges/")
    Paper = None

def main():
    print("=== AlgonovaX Runner Started ===")
    strategies_path = os.path.join(os.path.dirname(__file__), "strategies")
    if os.path.exists(strategies_path):
        strategies = [f for f in os.listdir(strategies_path) if f.endswith(".py")]
        print(f"Found strategies: {strategies}")
    else:
        print("No strategies folder found.")
    if Paper:
        try:
            paper_trader = Paper()
            print("Paper trader initialized successfully.")
        except Exception as e:
            print(f"Error initializing Paper trader: {e}")

if __name__ == "__main__":
    main()
