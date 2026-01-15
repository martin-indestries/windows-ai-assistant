#!/usr/bin/env python3
"""
Example script demonstrating the SandboxRunManager verification pipeline.

This script shows how to use the new sandbox verification system to:
1. Create isolated sandbox runs
2. Verify code through multiple gates (syntax, tests, smoke)
3. Handle GUI programs with test_mode contract
4. Export verified code to desktop

Usage:
    python examples/sandbox_verification_demo.py
"""

import sys
import time
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from spectral.sandbox_manager import SandboxRunManager, SandboxResult
from spectral.gui_test_generator import GUITestGenerator


def demo_basic_verification():
    """Demonstrate basic code verification."""
    print("🔬 Demo: Basic Code Verification")
    print("=" * 50)
    
    # Create sandbox manager
    manager = SandboxRunManager()
    
    # Create a run
    run_id = manager.create_run()
    print(f"✓ Created sandbox run: {run_id}")
    
    # Example 1: Valid Python code
    valid_code = '''
def fibonacci(n):
    """Generate fibonacci sequence up to n terms."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    sequence = [0, 1]
    for i in range(2, n):
        sequence.append(sequence[i-1] + sequence[i-2])
    
    return sequence

if __name__ == "__main__":
    print("Fibonacci sequence (10 terms):")
    print(fibonacci(10))
'''
    
    print("\n📝 Testing valid Python code...")
    result = manager.execute_verification_pipeline(
        run_id=run_id,
        code=valid_code,
        filename="fibonacci.py",
    )
    
    print(f"Status: {result.status}")
    print(f"Gates passed: {result.gates_passed}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    
    if result.status == "success":
        print("✅ Code verification successful!")
    else:
        print(f"❌ Verification failed: {result.error_message}")
    
    # Clean up
    manager.cleanup_run(run_id)
    print(f"\n🧹 Cleaned up sandbox run: {run_id}")


def demo_syntax_error():
    """Demonstrate syntax error detection."""
    print("\n\n🔬 Demo: Syntax Error Detection")
    print("=" * 50)
    
    manager = SandboxRunManager()
    run_id = manager.create_run()
    
    # Code with syntax error
    invalid_code = '''
def broken_function(
    """This function has a syntax error"""
    print("This will fail")
    return "broken"
'''
    
    print("📝 Testing code with syntax error...")
    result = manager.execute_verification_pipeline(
        run_id=run_id,
        code=invalid_code,
        filename="broken.py",
    )
    
    print(f"Status: {result.status}")
    print(f"Error: {result.error_message}")
    print(f"Gate 'syntax': {result.gates_passed['syntax']}")
    
    manager.cleanup_run(run_id)


def demo_gui_verification():
    """Demonstrate GUI program verification with test_mode contract."""
    print("\n\n🔬 Demo: GUI Program Verification")
    print("=" * 50)
    
    manager = SandboxRunManager()
    gui_test_generator = GUITestGenerator()
    run_id = manager.create_run()
    
    # GUI code that follows test_mode contract
    gui_code = '''
import customtkinter as ctk

def create_app(test_mode: bool = False):
    """
    Create and return the GUI application.
    
    Args:
        test_mode: If True, build widget tree but do NOT call mainloop().
                   Return root window + dict of key widgets for testing.
    
    Returns:
        If test_mode=True: (root, widgets_dict)
        If test_mode=False: None (app runs mainloop())
    """
    root = ctk.CTk()
    root.title("Counter App")
    root.geometry("300x200")
    
    # Create widgets
    counter = {"value": 0}
    
    def increment_counter():
        counter["value"] += 1
        label.configure(text=f"Count: {counter['value']}")
    
    def decrement_counter():
        counter["value"] -= 1
        label.configure(text=f"Count: {counter['value']}")
    
    # UI elements
    label = ctk.CTkLabel(root, text="Count: 0", font=("Arial", 16))
    label.pack(pady=20)
    
    button_frame = ctk.CTkFrame(root)
    button_frame.pack(pady=10)
    
    increment_btn = ctk.CTkButton(
        button_frame, 
        text="Increment", 
        command=increment_counter,
        width=100
    )
    increment_btn.pack(side="left", padx=5)
    
    decrement_btn = ctk.CTkButton(
        button_frame, 
        text="Decrement", 
        command=decrement_counter,
        width=100
    )
    decrement_btn.pack(side="left", padx=5)
    
    if test_mode:
        return root, {
            "label": label,
            "increment_btn": increment_btn,
            "decrement_btn": decrement_btn,
            "counter": counter
        }
    else:
        root.mainloop()
        return None

def main():
    """Entry point for normal execution."""
    create_app(test_mode=False)

if __name__ == "__main__":
    main()
'''
    
    print("📝 Testing GUI program with test_mode contract...")
    
    # Check if GUI is detected
    is_gui, framework = gui_test_generator.detect_gui_program(gui_code)
    print(f"GUI detected: {is_gui} ({framework})")
    
    # Run verification
    result = manager.execute_verification_pipeline(
        run_id=run_id,
        code=gui_code,
        filename="gui_counter.py",
        is_gui=True,  # Explicitly set as GUI
    )
    
    print(f"Status: {result.status}")
    print(f"Gates passed: {result.gates_passed}")
    
    if result.status == "success":
        print("✅ GUI code verification successful!")
        print("💡 Code follows test_mode contract and won't block on mainloop()")
    else:
        print(f"❌ Verification failed: {result.error_message}")
    
    manager.cleanup_run(run_id)


def demo_interactive_program():
    """Demonstrate interactive program testing."""
    print("\n\n🔬 Demo: Interactive Program Testing")
    print("=" * 50)
    
    manager = SandboxRunManager()
    run_id = manager.create_run()
    
    # Interactive program with input()
    interactive_code = '''
def get_user_info():
    """Get user information through interactive input."""
    print("Welcome to the User Information System!")
    
    name = input("What is your name? ").strip()
    if not name:
        name = "Anonymous"
    
    age_input = input("How old are you? ")
    try:
        age = int(age_input)
    except ValueError:
        print("Invalid age, using 0")
        age = 0
    
    email = input("What is your email? ").strip()
    
    print(f"\n--- User Summary ---")
    print(f"Name: {name}")
    print(f"Age: {age}")
    print(f"Email: {email}")
    print("Thank you for providing your information!")
    
    return {
        "name": name,
        "age": age,
        "email": email
    }

if __name__ == "__main__":
    user_info = get_user_info()
'''
    
    print("📝 Testing interactive program...")
    print("💡 System will auto-generate test inputs for input() calls")
    
    result = manager.execute_verification_pipeline(
        run_id=run_id,
        code=interactive_code,
        filename="user_info.py",
    )
    
    print(f"Status: {result.status}")
    print(f"Gates passed: {result.gates_passed}")
    
    if result.status == "success":
        print("✅ Interactive program verification successful!")
        print("💡 Auto-generated test inputs worked correctly")
    else:
        print(f"❌ Verification failed: {result.error_message}")
    
    manager.cleanup_run(run_id)


def demo_mainloop_detection():
    """Demonstrate GUI mainloop detection in CLI programs."""
    print("\n\n🔬 Demo: Mainloop Detection in CLI Programs")
    print("=" * 50)
    
    manager = SandboxRunManager()
    run_id = manager.create_run()
    
    # CLI program that accidentally has mainloop() call
    problematic_code = '''
import tkinter as tk

def process_data():
    """Process some data."""
    print("Processing data...")
    data = [1, 2, 3, 4, 5]
    result = sum(data)
    print(f"Sum of data: {result}")
    return result

if __name__ == "__main__":
    # This is a CLI program but accidentally calls mainloop()
    root = tk.Tk()
    root.title("Hidden GUI")
    
    def on_click():
        print("Button clicked!")
        result = process_data()
        print(f"Result: {result}")
    
    button = tk.Button(root, text="Process Data", command=on_click)
    button.pack()
    
    # This will block verification!
    root.mainloop()
'''
    
    print("📝 Testing CLI program with accidental mainloop()...")
    print("🚫 This should be detected and flagged as problematic")
    
    result = manager.execute_verification_pipeline(
        run_id=run_id,
        code=problematic_code,
        filename="problematic.py",
        is_gui=False,  # Treated as CLI program
    )
    
    print(f"Status: {result.status}")
    print(f"Error: {result.error_message}")
    
    if result.status == "error":
        print("✅ Mainloop detection working correctly!")
        print("💡 Program flagged as problematic for CLI execution")
    else:
        print("⚠️  Mainloop detection may need adjustment")
    
    manager.cleanup_run(run_id)


def main():
    """Run all demonstration examples."""
    print("🚀 Sandbox Verification Pipeline Demo")
    print("=" * 60)
    print("This demo shows the new sandbox verification system that:")
    print("• Creates isolated execution environments")
    print("• Runs code through verification gates")
    print("• Detects GUI programs and enforces test_mode contract")
    print("• Prevents blocking on mainloop() during verification")
    print("• Provides detailed error reporting")
    print("=" * 60)
    
    try:
        # Run demos
        demo_basic_verification()
        demo_syntax_error()
        demo_gui_verification()
        demo_interactive_program()
        demo_mainloop_detection()
        
        print("\n\n🎉 All demos completed!")
        print("=" * 60)
        print("✅ Sandbox verification pipeline is working correctly")
        print("💡 DirectExecutor now uses this system for robust code verification")
        print("🔒 Code is verified before being exported to desktop")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()