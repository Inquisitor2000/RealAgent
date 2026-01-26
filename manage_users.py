#!/usr/bin/env python3
"""
RealAgent User Management CLI
==============================

Interactive command-line tool to manage users in the RealAgent system.

Usage:
    python manage_users.py
"""

import sys
import getpass
from pathlib import Path

# Add Helper to path
sys.path.insert(0, str(Path(__file__).parent))
from Helper.database import (
    init_mainframe_db,
    create_user,
    list_users,
    change_password,
    authenticate_user
)


def clear_screen():
    """Clear the terminal screen."""
    import os
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header():
    """Print the application header."""
    print("\n" + "="*60)
    print("🏛️  RealAgent User Management")
    print("="*60 + "\n")


def print_users_table():
    """Print all users in a formatted table."""
    users = list_users()
    
    if not users:
        print("📭 No users found.\n")
        return
    
    print(f"{'ID':<5} {'Username':<15} {'Full Name':<20} {'Role':<10} {'Active':<8}")
    print("-"*60)
    
    for user in users:
        active = '✅' if user['active'] else '❌'
        full_name = (user['full_name'] or 'N/A')[:19]
        
        print(f"{user['id']:<5} {user['username']:<15} {full_name:<20} "
              f"{user['role']:<10} {active:<8}")
    
    print()


def show_menu():
    """Display the main menu and get user choice."""
    print("What would you like to do?")
    print()
    print("  1. 👥 List all users")
    print("  2. ➕ Create new user")
    print("  3. 🔐 Change password")
    print("  4. 🚪 Exit")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    return choice


def create_user_interactive():
    """Interactive user creation with minimal input."""
    print("\n" + "="*60)
    print("➕ Create New User")
    print("="*60 + "\n")
    
    # Username
    while True:
        username = input("Username: ").strip()
        if username:
            break
        print("❌ Username cannot be empty\n")
    
    # Password
    while True:
        password = getpass.getpass("Password (min 6 chars): ")
        if len(password) >= 6:
            break
        print("❌ Password must be at least 6 characters\n")
    
    # Full name (optional)
    full_name = input("Full name (optional, press Enter to skip): ").strip()
    
    # Role
    print("\nSelect role:")
    print("  1. Agent  (default) - Can create and edit own listings")
    print("  2. Admin  - Full access to everything")
    print("  3. Viewer - Read-only access")
    
    role_choice = input("\nRole (1-3) [1]: ").strip() or "1"
    role_map = {"1": "agent", "2": "admin", "3": "viewer"}
    role = role_map.get(role_choice, "agent")
    
    # Confirm
    print(f"\n📋 Summary:")
    print(f"   Username: {username}")
    print(f"   Full name: {full_name or 'N/A'}")
    print(f"   Role: {role}")
    
    confirm = input("\nCreate this user? (y/n) [y]: ").strip().lower() or "y"
    
    if confirm != 'y':
        print("❌ Cancelled\n")
        return
    
    # Create user
    result = create_user(username, password, full_name, role)
    
    if result['success']:
        print(f"\n✅ User '{username}' created successfully!")
        print(f"   User ID: {result['user_id']}")
        print(f"   Role: {role}\n")
    else:
        print(f"\n❌ Error: {result['error']}\n")


def change_password_interactive():
    """Interactive password change."""
    print("\n" + "="*60)
    print("🔐 Change Password")
    print("="*60 + "\n")
    
    # Show users
    print("Available users:")
    users = list_users()
    for i, user in enumerate(users, 1):
        print(f"  {i}. {user['username']} ({user['full_name'] or 'No name'})")
    
    print()
    
    # Select user
    while True:
        choice = input(f"Select user (1-{len(users)}) or enter username: ").strip()
        
        # Check if it's a number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(users):
                username = users[idx]['username']
                break
        # Check if it's a username
        elif any(u['username'] == choice for u in users):
            username = choice
            break
        
        print(f"❌ Invalid choice. Try again.\n")
    
    print(f"\nChanging password for: {username}")
    
    # Current password
    old_password = getpass.getpass("Current password: ")
    
    # New password
    while True:
        new_password = getpass.getpass("New password (min 6 chars): ")
        if len(new_password) >= 6:
            break
        print("❌ Password must be at least 6 characters\n")
    
    # Confirm new password
    new_password_confirm = getpass.getpass("Confirm new password: ")
    
    if new_password != new_password_confirm:
        print("\n❌ Passwords don't match\n")
        return
    
    # Change password
    result = change_password(username, old_password, new_password)
    
    if result['success']:
        print(f"\n✅ Password changed successfully for '{username}'\n")
    else:
        print(f"\n❌ Error: {result['error']}\n")


def main():
    """Main interactive CLI loop."""
    # Initialize database
    init_mainframe_db()
    
    while True:
        clear_screen()
        print_header()
        
        choice = show_menu()
        
        if choice == '1':
            # List users
            clear_screen()
            print_header()
            print("👥 All Users\n")
            print_users_table()
            input("Press Enter to continue...")
        
        elif choice == '2':
            # Create user
            clear_screen()
            print_header()
            create_user_interactive()
            input("Press Enter to continue...")
        
        elif choice == '3':
            # Change password
            clear_screen()
            print_header()
            change_password_interactive()
            input("Press Enter to continue...")
        
        elif choice == '4':
            # Exit
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("\n❌ Invalid choice. Please enter 1-4.\n")
            input("Press Enter to continue...")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
