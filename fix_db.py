#!/usr/bin/env python3
"""
Fix Database - Mark all existing users as verified
"""

from website import create_app, db
from website.models import User

app = create_app()

with app.app_context():
    print("\n" + "="*70)
    print("FIXING DATABASE - Marking all users as verified")
    print("="*70 + "\n")
    
    users = User.query.all()
    print(f"Found {len(users)} users")
    
    updated = 0
    for user in users:
        if not user.is_verified:
            user.is_verified = True
            updated += 1
            print(f"  ✓ Verified: {user.email}")
    
    if updated > 0:
        db.session.commit()
        print(f"\n✅ Updated {updated} users to verified status")
    else:
        print("\n✅ All users already verified")
    
    # Show all users
    print("\n" + "-"*70)
    print("All Users:")
    print("-"*70)
    users = User.query.all()
    for user in users:
        print(f"  Email: {user.email}")
        print(f"    Verified: {user.is_verified}")
        print(f"    Created: {user.created_at}\n")
    
    print("="*70)
