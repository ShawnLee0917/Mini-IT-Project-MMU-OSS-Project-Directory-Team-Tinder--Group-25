#!/usr/bin/env python3
"""
Admin System Setup Script
Quick setup for admin content moderation system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from website import create_app, db
from website.models import User, ContentFlagKeyword, SuspendedUser

def setup_admin_system():
    """Initialize admin moderation system"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*60)
        print("🛡️  Admin Content Moderation System Setup")
        print("="*60 + "\n")
        
        # Step 1: Set up admin user
        print("[STEP 1] Setting up admin account")
        print("-" * 60)
        email = input("Enter admin email (e.g., admin@mmu.edu.my): ").strip().lower()
        
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"❌ ERROR: User {email} not found")
            print("Please register the account first")
            return
        
        if user.is_admin:
            print(f"✓ {email} is already an admin")
        else:
            user.is_admin = True
            db.session.commit()
            print(f"✓ Successfully set {email} as admin")
        
        # Step 2: Add default flagged keywords
        print("\n[STEP 2] Adding default flagged keywords")
        print("-" * 60)
        
        default_keywords = [
            # ==== English Spam Keywords ====
            {'keyword': 'click-here', 'category': 'spam', 'severity': 2},
            {'keyword': 'buy-now', 'category': 'spam', 'severity': 3},
            {'keyword': 'free-money', 'category': 'spam', 'severity': 4},
            {'keyword': 'earn-cash', 'category': 'spam', 'severity': 3},
            {'keyword': 'whatsapp-group', 'category': 'spam', 'severity': 3},
            {'keyword': 'crypto-investment', 'category': 'spam', 'severity': 4},
            
            # ==== English Academic Integrity Keywords ====
            {'keyword': 'assignment-help', 'category': 'harmful', 'severity': 4},
            {'keyword': 'cheat-exam', 'category': 'harmful', 'severity': 5},
            
            # ==== Inappropriate Keywords ====
            {'keyword': 'inappropriate', 'category': 'inappropriate', 'severity': 3},
            {'keyword': 'harmful-content', 'category': 'harmful', 'severity': 5},
            {'keyword': 'scam', 'category': 'inappropriate', 'severity': 4},
            
            # ==== Chinese Flagged Keywords (Fully Supported) ====
            {'keyword': '代写', 'category': 'harmful', 'severity': 5},
            {'keyword': '代刷', 'category': 'harmful', 'severity': 4},
            {'keyword': '加微信', 'category': 'spam', 'severity': 3},
            {'keyword': '兼职赚钱', 'category': 'spam', 'severity': 3},
            {'keyword': '作弊', 'category': 'harmful', 'severity': 5}
        ]

        added_count = 0
        for kw_data in default_keywords:
            existing = ContentFlagKeyword.query.filter_by(keyword=kw_data['keyword']).first()
            if not existing:
                new_kw = ContentFlagKeyword(
                    keyword=kw_data['keyword'],
                    category=kw_data['category'],
                    severity=kw_data['severity']
                )
                db.session.add(new_kw)
                added_count += 1
                print(f"  ✓ Added keyword: '{kw_data['keyword']}' ({kw_data['category']})")
            else:
                print(f"  - Skipped (already exists): '{kw_data['keyword']}'")

        db.session.commit()
        print(f"✓ Total new keywords added: {added_count}")
        
        # Step 3: Display admin access info
        print("\n[STEP 3] Admin dashboard access")
        print("-" * 60)
        print(f"✓ Admin user: {email}")
        print(f"✓ Access URL: http://localhost:5000/admin/dashboard")
        print(f"✓ Log in with the admin account")
        
        # Step 4: Quick stats
        print("\n[SYSTEM STATISTICS]")
        print("-" * 60)
        total_users = User.query.count()
        admin_users = User.query.filter_by(is_admin=True).count()
        total_keywords = ContentFlagKeyword.query.filter_by(is_active=True).count()
        
        print(f"Total users: {total_users}")
        print(f"Admin users: {admin_users}")
        print(f"Active keywords: {total_keywords}")
        
        print("\n" + "="*60)
        print("✅ System setup complete!")
        print("="*60 + "\n")
        
        # Display API examples
        print("[QUICK COMMAND EXAMPLES]\n")
        print("1️⃣  Add keyword (admin panel):")
        print("   POST /api/admin/add-keyword")
        print("   {'keyword': '..', 'category': 'spam', 'severity': 3}\n")
        
        print("2️⃣  User report content:")
        print("   POST /api/report-content")
        print("   {'content_type': 'post', 'content_id': 123, 'reason': 'spam'}\n")
        
        print("3️⃣  Approve report and delete content:")
        print("   POST /api/admin/approve-report/123")
        print("   {'comment': 'Violates community guidelines'}\n")
        
        print("For more details, please check: ADMIN_MODERATION_GUIDE.md\n")

if __name__ == '__main__':
    setup_admin_system()
