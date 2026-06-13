"""
Seed script to populate the database with initial data for development/demo.
Run: python seed.py
"""
from database import SessionLocal, engine, Base
from models import User, Category, Ticket, Comment
from auth import hash_password

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Check if data already exists
    if db.query(User).first():
        print("Database already seeded. Skipping.")
    else:
        print("Seeding database...")

        # ── Create Users ────────────────────────────────
        customers = [
            User(name="Rahul Sharma", email="rahul@example.com",
                 password_hash=hash_password("password123"), role="customer"),
            User(name="Priya Patel", email="priya@example.com",
                 password_hash=hash_password("password123"), role="customer"),
            User(name="Amit Kumar", email="amit@example.com",
                 password_hash=hash_password("password123"), role="customer"),
        ]
        agents = [
            User(name="Som Tomar", email="som@support.com",
                 password_hash=hash_password("password123"), role="agent"),
            User(name="Neha Singh", email="neha@support.com",
                 password_hash=hash_password("password123"), role="agent"),
        ]
        db.add_all(customers + agents)
        db.commit()
        print(f"  Created {len(customers)} customers and {len(agents)} agents")

        # ── Create Categories ───────────────────────────
        categories = [
            Category(name="Billing", description="Payment, invoicing, and subscription issues"),
            Category(name="Technical", description="Bugs, errors, and technical problems"),
            Category(name="Account", description="Login, profile, and account management"),
            Category(name="Feature Request", description="New feature suggestions and improvements"),
            Category(name="General", description="General inquiries and other topics"),
        ]
        db.add_all(categories)
        db.commit()
        print(f"  Created {len(categories)} categories")

        # ── Create Sample Tickets ───────────────────────
        tickets = [
            Ticket(
                title="Unable to process payment on checkout",
                description="I've been trying to complete my purchase for the last 2 hours but the payment keeps failing. I've tried Visa and Mastercard. Error says 'Payment gateway timeout'. This is urgent as I need the service activated by tomorrow.",
                status="open", priority="urgent",
                customer_id=1, category_id=1,
            ),
            Ticket(
                title="Dashboard charts not loading on Firefox",
                description="The analytics dashboard charts are showing as blank white boxes on Firefox 120. Works fine on Chrome. Dev console shows 'Canvas rendering context error'. Attached screenshot in the comments.",
                status="in_progress", priority="medium",
                customer_id=2, agent_id=4, category_id=2,
            ),
            Ticket(
                title="Request to change account email address",
                description="I'd like to update my account email from oldmail@example.com to newemail@example.com. I recently changed my email provider and want to make sure I continue receiving notifications.",
                status="open", priority="low",
                customer_id=3, category_id=3,
            ),
            Ticket(
                title="Add dark mode support to the platform",
                description="Would love to see a dark mode option for the platform. I use it late at night and the bright white background is hard on the eyes. Many modern platforms support this feature.",
                status="open", priority="low",
                customer_id=1, category_id=4,
            ),
            Ticket(
                title="API rate limit exceeded unexpectedly",
                description="Our integration started hitting 429 errors today. We haven't changed our usage pattern and are well within the documented rate limits (100 req/min). The errors started around 2 PM IST. Our API key is XK-****-7892.",
                status="in_progress", priority="medium",
                customer_id=2, agent_id=5, category_id=2,
            ),
            Ticket(
                title="Subscription renewal confirmation not received",
                description="My annual subscription renewed 3 days ago (charged to my card) but I haven't received any confirmation email. My account shows 'Active' but I want documentation for my records.",
                status="resolved", priority="medium",
                customer_id=3, agent_id=4, category_id=1,
            ),
        ]
        db.add_all(tickets)
        db.commit()
        print(f"  Created {len(tickets)} sample tickets")

        # ── Create Sample Comments ──────────────────────
        sample_comments = [
            Comment(content="I've tried clearing my browser cache and cookies but the payment still fails. Please help!", ticket_id=1, user_id=1),
            Comment(content="Hi Rahul, looking into this issue now. Can you confirm which browser and version you're using?", ticket_id=2, user_id=4),
            Comment(content="I'm using Firefox 120.0.1 on Windows 11. The issue started yesterday after updating Firefox.", ticket_id=2, user_id=2),
            Comment(content="Thanks for the details. This looks like a known issue with Firefox's WebGL implementation. We're pushing a fix that uses a 2D canvas fallback.", ticket_id=2, user_id=4),
            Comment(content="The issue has been resolved and the confirmation email has been resent. Please check your inbox and spam folder.", ticket_id=6, user_id=4),
            Comment(content="Got it! Thank you for the quick resolution.", ticket_id=6, user_id=3),
        ]
        db.add_all(sample_comments)
        db.commit()
        print(f"  Created {len(sample_comments)} sample comments")

        print("\nSeed complete! Demo accounts:")
        print("  Customers: rahul@example.com / priya@example.com / amit@example.com")
        print("  Agents:    som@support.com / neha@support.com")
        print("  Password:  password123 (for all accounts)")

finally:
    db.close()
