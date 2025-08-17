#!/usr/bin/env python3
"""
Simple helper script to list all GroupMe groups the current user is in.
"""

from groupme.groupme_interface import GroupMeInterface

def main():
    try:
        # Initialize interface
        interface = GroupMeInterface()
        
        # Get all groups
        groups = interface.get_user_groups()
        
        print(f"Found {len(groups)} groups:")
        print("-" * 50)
        
        for i, group in enumerate(groups, 1):
            group_name = group.get('name', 'Unknown')
            group_id = group.get('id')
            member_count = group.get('members', [])
            print(f"{i}. {group_name}")
            print(f"   ID: {group_id}")
            print(f"   Members: {len(member_count)}")
            print()
            
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
