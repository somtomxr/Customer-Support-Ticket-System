"""
rich_seed.py
============
Seeds 120 realistic support tickets across 6 semantic clusters so the
sentence-transformer similarity engine has enough data to be genuinely useful.

Clusters (tickets will score high similarity within each group):
  A. Login / Authentication (20 tickets)
  B. Payment / Billing      (20 tickets)
  C. Technical / App bugs   (20 tickets)
  D. Account management     (20 tickets)
  E. Performance / Outage   (20 tickets)
  F. Feature requests       (20 tickets)

Run: python rich_seed.py
"""

import random
from datetime import datetime, timedelta
from database import SessionLocal, engine, Base
from models import User, Category, Ticket, Comment
from auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Wipe existing tickets + comments (keep users & categories) ─────────────────
print("Clearing old tickets and comments...")
db.query(Comment).delete()
db.query(Ticket).delete()
db.commit()

# ── Ensure users exist ──────────────────────────────────────────────────────────
def get_or_create_user(name, email, role):
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(name=name, email=email, password_hash=hash_password("password123"), role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
    return u

customers = [
    get_or_create_user("Rahul Sharma",  "rahul@example.com",  "customer"),
    get_or_create_user("Priya Patel",   "priya@example.com",  "customer"),
    get_or_create_user("Amit Kumar",    "amit@example.com",   "customer"),
    get_or_create_user("Sneha Reddy",   "sneha@example.com",  "customer"),
    get_or_create_user("Vikram Singh",  "vikram@example.com", "customer"),
]

agents = [
    get_or_create_user("Som Tomar",  "som@support.com",  "agent"),
    get_or_create_user("Neha Gupta", "neha@support.com", "agent"),
]

# ── Ensure categories exist ─────────────────────────────────────────────────────
def get_or_create_cat(name, desc):
    c = db.query(Category).filter(Category.name == name).first()
    if not c:
        c = Category(name=name, description=desc)
        db.add(c)
        db.commit()
        db.refresh(c)
    return c

cat_billing   = get_or_create_cat("Billing",     "Payment, invoice, and subscription issues")
cat_technical = get_or_create_cat("Technical",   "App bugs, errors, and integrations")
cat_account   = get_or_create_cat("Account",     "Profile, login, and account settings")
cat_general   = get_or_create_cat("General",     "General questions and feature requests")
cat_perf      = get_or_create_cat("Performance", "Slowness, outages, and reliability issues")

# ── Ticket definitions ──────────────────────────────────────────────────────────
# Each entry: (title, description, priority, category, status, resolution_comment)
# status: "open" | "in_progress" | "resolved"
# resolution_comment: None or string (added as agent comment if resolved)

TICKETS = [

  # ══ CLUSTER A: Login / Authentication (20) ═══════════════════════════════════

  ("Cannot login after password reset",
   "I used the forgot password link and reset my password. But when I try to login with the new password it says invalid credentials. I have tried 5 times and also tried on a different browser. Nothing works.",
   "urgent", cat_account, "resolved",
   "Hi! This is a known issue when the password reset link is used more than once. Please clear your browser cookies and try logging in at a private/incognito window. If still stuck, I have manually cleared the session from our end — please try now."),

  ("Account locked after too many login attempts",
   "I forgot my password and tried too many times. Now it says my account is locked and I cannot even use the forgot password link. I need access urgently for a work deadline.",
   "urgent", cat_account, "resolved",
   "Account has been unlocked from our side. You will receive a password reset email in the next 2 minutes. Please use it within 15 minutes as the link expires."),

  ("Two-factor authentication code not arriving",
   "I enabled 2FA on my account but now the SMS code never arrives. I have waited 10 minutes. I cannot login at all because it keeps asking for the code.",
   "urgent", cat_account, "resolved",
   "There was a delay with our SMS provider. As an immediate fix we have sent the 2FA code to your registered email instead. We have also temporarily switched your 2FA to email-based. You can reconfigure SMS in settings once logged in."),

  ("Google login stopped working suddenly",
   "I always login using my Google account. Today when I click Sign in with Google it shows an error saying 'access denied'. I have not changed anything on my Google account.",
   "medium", cat_account, "in_progress",
   None),

  ("Login page shows blank white screen",
   "When I go to the login page I just see a white screen. Nothing loads. I tried Chrome, Firefox, and Safari. All the same. My colleague can login fine from the same wifi.",
   "medium", cat_technical, "resolved",
   "This was caused by a corrupted cache entry for your account. We have cleared it from our CDN. Please hard-refresh (Ctrl+Shift+R) and try again — it should work now."),

  ("Session keeps expiring every 5 minutes",
   "Every few minutes I get logged out automatically and have to login again. This is extremely disruptive when I am in the middle of filling a form. It only started happening this week.",
   "medium", cat_account, "in_progress",
   None),

  ("Password reset email never arrives",
   "I have clicked forgot password three times and the reset email never arrives. I checked my spam folder too. My email is correct because I receive other emails from your service fine.",
   "urgent", cat_account, "resolved",
   "We found the reset emails were being flagged by your corporate email gateway. We have sent the reset link directly to your personal email on file. Also whitelisting our domain (noreply@supportdesk.io) in your email settings will prevent this in future."),

  ("Cannot change my account password",
   "I go to Settings > Security > Change Password, enter my current password and the new one, click save, and nothing happens. No error message, the page just refreshes and the password is unchanged.",
   "low", cat_account, "open",
   None),

  ("Login works on mobile but not on desktop",
   "I can login perfectly fine on my phone app but when I try on my laptop browser it always says incorrect password even though I am copy-pasting the exact same credentials.",
   "medium", cat_account, "resolved",
   "This was a browser extension conflict — likely a password manager auto-filling an old password. Please disable all extensions and try in incognito mode. That should resolve it immediately."),

  ("Account shows logged in from unknown location",
   "I got an email saying someone logged into my account from Mumbai but I am in Delhi. I did not do this login. Please help me secure my account immediately.",
   "urgent", cat_account, "resolved",
   "We have immediately terminated all active sessions on your account and sent a security alert. Please reset your password now. We have also enabled login notifications for any future access. Our security team has flagged this IP for investigation."),

  ("SSO login with company account not working",
   "Our company uses SSO for all internal tools. Your platform is configured with our SSO but today it stopped accepting our company login. Our IT says nothing changed on their end.",
   "urgent", cat_account, "in_progress",
   None),

  ("New user cannot complete account registration",
   "I signed up yesterday but never received the email verification link. My account is stuck in unverified state and I cannot access any features.",
   "medium", cat_account, "resolved",
   "Verification email has been resent and your account has been manually verified from our side. You should be able to login immediately now."),

  ("Biometric login on mobile app not working",
   "The fingerprint login on the mobile app stopped working after the latest update. It just shows an error and I have to type my password every time. Quite annoying.",
   "low", cat_technical, "open",
   None),

  ("Login redirect loop after OAuth",
   "When I try to login with my Microsoft account it keeps redirecting back and forth between your site and Microsoft login page endlessly. Never actually logs me in.",
   "urgent", cat_account, "resolved",
   "The OAuth redirect URI was misconfigured after our recent domain migration. This has been fixed. Microsoft login should work correctly now — please try again."),

  ("Forgot password link says link expired immediately",
   "As soon as I click the forgot password link in the email it says the link has expired. I am clicking it within seconds of receiving the email.",
   "urgent", cat_account, "resolved",
   "The links were generated with a timezone bug that made them expire immediately for users in IST (UTC+5:30). This has been patched. A new reset email has been sent — this one will work."),

  ("Cannot login on company VPN",
   "I can login normally when not on VPN but as soon as I connect to company VPN the login fails with a 403 error. My colleagues on the same VPN also face this.",
   "urgent", cat_account, "in_progress",
   None),

  ("Account email changed without my permission",
   "I received an email saying my account email was changed. I did not do this. Someone may have accessed my account. Please revert immediately and secure my account.",
   "urgent", cat_account, "resolved",
   "We have reverted the email change, locked the account, terminated all sessions, and escalated to our security team. You will receive an account recovery email on your original address in the next 5 minutes."),

  ("Login works but dashboard shows another user's data",
   "I logged in successfully but my dashboard shows what looks like a completely different person's tickets and profile. My name at top is wrong too.",
   "urgent", cat_technical, "resolved",
   "This was a critical session caching bug affecting a small number of users. We have immediately patched the issue, cleared all cached sessions, and audited the affected accounts. Your account is now correctly isolated. We sincerely apologize for this."),

  ("Cannot login after switching to new phone number",
   "I changed my phone number and updated it in my profile. But now when 2FA sends the code it goes to my OLD number which I no longer have access to.",
   "urgent", cat_account, "resolved",
   "We have bypassed 2FA for your account and sent a recovery code to your registered email. Once logged in, please update your phone number in Security Settings and re-enroll 2FA with the new number."),

  ("Username taken error on a username I have always used",
   "I was trying to update my username but it says the username is taken — but it is my own current username! I am trying to re-save it without actually changing it.",
   "low", cat_account, "resolved",
   "This is a known UI bug where re-saving the same username triggers a duplicate check against itself. Fixed in the UI now. As a workaround you can change to a temporary name, save, then change back."),


  # ══ CLUSTER B: Payment / Billing (20) ════════════════════════════════════════

  ("Charged twice for same subscription",
   "I see two charges of Rs 999 on my credit card statement for this month from your service. I should only be charged once. Please refund the duplicate charge.",
   "urgent", cat_billing, "resolved",
   "Confirmed the duplicate charge — this was caused by a payment retry during a brief network interruption. A full refund of Rs 999 has been initiated and will reflect in 5-7 business days. Apologies for the inconvenience."),

  ("Payment failed but money deducted from account",
   "I tried to pay for the annual plan. Your site showed payment failed but my bank shows the money was deducted. Order still shows unpaid on your side.",
   "urgent", cat_billing, "resolved",
   "We can see the payment was captured on our payment gateway but the webhook failed to update your order. Your account has been manually upgraded to annual plan. The payment was successful — no further action needed on your end."),

  ("Cannot update credit card details",
   "My old credit card expired and I am trying to add my new card. The form accepts the details but when I save it shows a generic error. I have tried 4 different times.",
   "medium", cat_billing, "resolved",
   "There was a validation bug rejecting cards with certain BIN ranges. This has been fixed. Your new card has been added manually — please verify it shows correctly in your billing settings."),

  ("Refund not received after 30 days",
   "I cancelled my subscription on May 1st and was promised a refund within 7-10 business days. It is now June 1st and I still have not received any refund. My bank says nothing is pending from your side.",
   "medium", cat_billing, "resolved",
   "We sincerely apologize. We found the refund was initiated but stuck in a failed state due to a bank API issue. A fresh refund has been processed today and should arrive in 3-5 business days. You will receive a confirmation email."),

  ("Invoice shows wrong company name",
   "The invoices you generate show my personal name instead of my company name. I need correct GST invoices with my company name for tax purposes. This has been wrong for 3 months.",
   "medium", cat_billing, "in_progress",
   None),

  ("Cannot download GST invoice",
   "I need the GST invoice for my subscription for tax filing. When I go to Billing > Invoices and click download it just shows a loading spinner forever and nothing downloads.",
   "medium", cat_billing, "resolved",
   "The invoice PDF generation was timing out for accounts with more than 12 months of history. This has been fixed. All your invoices are now downloadable. Links sent to your email as well."),

  ("Subscription auto-renewed without notice",
   "My annual subscription renewed today and Rs 11988 was charged without any advance notice or reminder email. I wanted to cancel before renewal. Please refund as I no longer need the service.",
   "urgent", cat_billing, "in_progress",
   None),

  ("Wrong plan applied after upgrade payment",
   "I paid for the Professional plan upgrade but my account still shows Basic plan. It has been 2 hours since payment. I need the Pro features urgently.",
   "urgent", cat_billing, "resolved",
   "Your account has been manually upgraded to Professional plan. The delay was due to a payment webhook processing issue that has now been fixed. You should see all Pro features immediately."),

  ("UPI payment failing repeatedly",
   "I am trying to pay using Google Pay UPI but every attempt fails. It says payment declined but no money is being deducted. I have enough balance. I have tried 6 times.",
   "medium", cat_billing, "resolved",
   "Our UPI payment processor was experiencing intermittent failures for GPay specifically. The issue has been resolved. Please try again — it should work now. Alternatively, you can also pay via net banking or card."),

  ("Coupon code not working at checkout",
   "I have a valid coupon code SAVE30 that was emailed to me by your team but when I enter it at checkout it says invalid coupon. The email clearly says it is valid till December 2026.",
   "low", cat_billing, "resolved",
   "Apologies — the coupon was not activated in our system despite being sent out. It has been activated now. Additionally, we have applied the 30% discount directly to your account for the next billing cycle as compensation for the inconvenience."),

  ("Billed for users I already removed",
   "I removed 3 users from my team 2 months ago but I am still being charged for 8 seats when I only have 5 active users. Please adjust my billing and refund the overcharge.",
   "medium", cat_billing, "resolved",
   "Confirmed the billing discrepancy. Seat count has been corrected to 5. A credit of Rs 4796 (2 months × 3 seats) has been applied to your account and will offset future invoices."),

  ("Free trial ended but I was not notified",
   "My free trial ended and I was immediately charged for a paid plan without any warning. I was not ready to subscribe yet. I would like a refund.",
   "medium", cat_billing, "in_progress",
   None),

  ("Partial payment showing as full payment",
   "I paid Rs 500 towards my outstanding balance of Rs 1200 but the system is showing the full balance as paid. I still owe Rs 700 and am worried about account suspension.",
   "medium", cat_billing, "resolved",
   "We found a display bug in the billing portal showing incorrect balance. Your actual outstanding balance of Rs 700 has been correctly recorded. The display issue has been fixed and your account status is fine."),

  ("International payment not accepted",
   "I am trying to pay from a US Visa card but keep getting a payment failed error. The card works on every other Indian website. Is there a restriction on international cards?",
   "medium", cat_billing, "resolved",
   "International cards now supported. The restriction was an oversight in our payment gateway configuration. Your US Visa card should work now. We have also enabled PayPal as an alternative option."),

  ("No invoice received for last 3 months",
   "I pay monthly but have not received any invoice emails for March, April, or May. My payments went through but I need the invoices for my company accounts.",
   "low", cat_billing, "resolved",
   "Invoice emails were being sent to your old email address. Updated to your current email and resent all 3 missing invoices. Going forward all invoices will arrive at the correct address."),

  ("Annual plan cancelled mid-year, need prorated refund",
   "I need to cancel my annual subscription 6 months early due to business reasons. I believe I am entitled to a prorated refund for the remaining 6 months as per your policy.",
   "medium", cat_billing, "in_progress",
   None),

  ("Payment page crashes on mobile browser",
   "When I try to complete payment on Safari mobile browser the page freezes and crashes just before the payment goes through. I can never complete the payment on mobile.",
   "medium", cat_billing, "resolved",
   "Safari mobile payment crash has been fixed in our latest frontend update. Please clear your Safari cache and try again. If you paid multiple times during the attempts, we will refund any duplicate charges."),

  ("Wrong currency being charged",
   "I am based in India and signed up for the INR plan but I am being charged in USD which is causing currency conversion fees from my bank. Please fix my billing currency.",
   "medium", cat_billing, "resolved",
   "Currency has been corrected to INR for your account. Going forward all charges will be in INR. Any conversion fees already incurred will be credited to your account balance."),

  ("Cannot cancel subscription online",
   "The cancel subscription button in my account settings does nothing when I click it. I have tried 3 browsers. I do not want to be charged next month.",
   "medium", cat_billing, "resolved",
   "The cancel button had a JavaScript error in specific account configurations. Fixed now. However, we have also gone ahead and cancelled your subscription immediately as requested. You will not be charged next month."),

  ("Payment receipt not matching actual charge",
   "The receipt you emailed says Rs 799 but my bank statement shows Rs 823 was charged. There is a Rs 24 difference I cannot explain.",
   "low", cat_billing, "resolved",
   "The Rs 24 difference is an 18% GST applied at the bank level for international payment processing. This is not charged by us. The receipt shows the base amount and the bank adds GST separately. This is standard RBI regulation. Happy to send a detailed breakdown."),


  # ══ CLUSTER C: Technical / App Bugs (20) ════════════════════════════════════

  ("App crashes immediately on launch",
   "After the latest update my Android app crashes as soon as I open it. I see the splash screen for a second then it closes. I have tried reinstalling 3 times. Nothing works.",
   "urgent", cat_technical, "resolved",
   "The v2.4.1 update had a compatibility issue with Android 12 devices. Hotfix v2.4.2 is now available on Play Store. Please update and the crash should be resolved."),

  ("Data not syncing between mobile and web",
   "Changes I make on the mobile app do not appear on the web dashboard and vice versa. I have to refresh manually and sometimes data is lost entirely.",
   "urgent", cat_technical, "in_progress",
   None),

  ("File upload failing for PDFs over 5MB",
   "I am trying to attach a PDF document to my ticket but it keeps failing with a generic error. The file is 8MB. I tested with a 2MB file and that worked fine.",
   "medium", cat_technical, "resolved",
   "File size limit has been increased to 25MB. The previous 5MB limit was too restrictive for common use cases. Your 8MB PDF should now upload without issues."),

  ("Search functionality returns no results",
   "The search bar in the dashboard is completely broken. I type anything and it just shows no results found even for tickets that clearly exist. It was working last week.",
   "medium", cat_technical, "resolved",
   "A bad database index migration caused the search to fail. The index has been rebuilt and search is fully functional again. All your tickets are correctly indexed now."),

  ("Email notifications not being sent",
   "I am not receiving any email notifications for ticket updates. My colleague is getting them fine. I have checked my notification settings and everything is enabled.",
   "medium", cat_technical, "resolved",
   "Your email address was accidentally added to our suppression list after an old bounce. Removed from suppression list — you will now receive all notifications. Test email sent to confirm delivery."),

  ("Dashboard shows outdated data",
   "The numbers on my dashboard are wrong. It shows 3 open tickets but I have 7. The charts are also showing last month's data. It seems like the dashboard is cached and not refreshing.",
   "medium", cat_technical, "resolved",
   "Dashboard caching was incorrectly set to 24 hours. Reduced to 5 minutes and manually purged your cached data. Your dashboard should now show real-time accurate numbers."),

  ("API returns 500 error on ticket creation endpoint",
   "We are integrating your API into our system and the POST /api/tickets endpoint is returning 500 Internal Server Error intermittently. It works sometimes and fails randomly.",
   "urgent", cat_technical, "in_progress",
   None),

  ("Rich text editor loses formatting on save",
   "When I write a ticket description with bullet points and bold text, the formatting disappears after saving. It saves as plain text. This makes long descriptions very hard to read.",
   "medium", cat_technical, "open",
   None),

  ("Attachments not visible to agent after ticket creation",
   "I attached 3 screenshots when creating a ticket but the agent who picked it up says they cannot see any attachments. The attachments show on my end.",
   "medium", cat_technical, "resolved",
   "There was a permissions bug where attachments were stored as private by default. All existing attachments have been made visible to agents. New attachments will work correctly going forward."),

  ("Date picker shows wrong dates in calendar",
   "The date picker in the filter section is off by one day. When I select June 10th it actually filters June 9th results. Very confusing for date-based reports.",
   "low", cat_technical, "resolved",
   "Classic timezone offset bug — dates were being stored in UTC but displayed assuming IST without conversion. Fixed. All date filters now correctly account for IST timezone."),

  ("Copy-paste not working in text fields",
   "I cannot paste text into any input field in the web app using Ctrl+V. I can type manually but paste does not work. This makes it very slow to fill in details.",
   "low", cat_technical, "resolved",
   "This was caused by a content security policy (CSP) header that was too restrictive and blocked clipboard access. Updated the CSP configuration — paste should work normally now."),

  ("Mobile app not working on iOS 17",
   "After updating my iPhone to iOS 17 the app stopped working completely. Shows a blank screen. Other apps work fine. Please fix iOS 17 compatibility.",
   "urgent", cat_technical, "in_progress",
   None),

  ("Export to CSV missing half the columns",
   "When I export my tickets to CSV the downloaded file only has 4 columns but there should be 12. Important fields like description and comments are missing.",
   "medium", cat_technical, "resolved",
   "The CSV export was using an outdated schema that only included legacy fields. Updated to include all current fields. Please re-export — you should see all 12 columns now."),

  ("Push notifications not arriving on Android",
   "I have enabled push notifications in the app and in my phone settings but I never receive any push notifications. My friend with iPhone gets them fine.",
   "low", cat_technical, "open",
   None),

  ("Dark mode has unreadable white text on white background",
   "Several screens in dark mode have white text against light grey or white backgrounds making them completely unreadable. Specifically the ticket list and profile page.",
   "low", cat_technical, "resolved",
   "Dark mode color contrast issues have been fixed in the latest release. All text should now meet WCAG AA accessibility standards in dark mode."),

  ("Bulk action on tickets not working",
   "I am trying to select multiple tickets and close them all at once using the bulk action menu but clicking the checkboxes selects only one ticket at a time and the bulk menu never appears.",
   "medium", cat_technical, "open",
   None),

  ("Webhook delivery failing with 401 errors",
   "Our webhook endpoint is receiving 401 Unauthorized errors from your service even though we configured the webhook secret correctly. Events are not being delivered.",
   "urgent", cat_technical, "resolved",
   "The webhook signing was using HMAC-SHA1 but your endpoint expected HMAC-SHA256. Updated the signing algorithm for your webhook configuration. Events should now deliver successfully."),

  ("Auto-save not working in ticket editor",
   "The ticket editor is supposed to auto-save drafts but I have lost my work twice when the browser refreshed. The auto-save timer in the corner shows it is saving but nothing is actually saved.",
   "medium", cat_technical, "open",
   None),

  ("Cannot delete a comment I posted by mistake",
   "I accidentally posted a comment with sensitive information. I need to delete it immediately but there is no delete option on my own comments. Please help urgently.",
   "urgent", cat_technical, "resolved",
   "The comment has been immediately deleted from our end. Comment deletion has been added to the product roadmap and will be available in the next release. For urgent cases please contact support directly as we can action it immediately."),

  ("Images in ticket descriptions not displaying",
   "I pasted screenshots directly into the ticket description but they just show as broken image icons to the recipient even though they look fine on my end when I created the ticket.",
   "medium", cat_technical, "resolved",
   "Pasted images were being stored as base64 inline which had a size limit. They are now correctly uploaded to our CDN and linked. Existing tickets with broken images have been migrated."),


  # ══ CLUSTER D: Account Management (20) ═══════════════════════════════════════

  ("How to add team members to my account",
   "I have a team of 5 people who need access to our shared account. I cannot figure out how to invite them. There is a Team section but the invite button does nothing.",
   "low", cat_account, "resolved",
   "The Team invite feature requires the Professional plan or higher. On your current Basic plan you can have 1 user. If you upgrade, you can invite up to 10 team members. Happy to help with the upgrade if needed."),

  ("Need to transfer account ownership to colleague",
   "I am leaving the company and need to transfer the account ownership to my colleague before I leave. My last day is Friday. Please help urgently.",
   "urgent", cat_account, "resolved",
   "Account ownership has been transferred to the new owner email you provided. They will receive an email with instructions. Your account access has been retained as a standard member until your requested date."),

  ("Cannot change my registered email address",
   "I changed jobs and need to update my email from my company email to personal email. When I try to update it asks for verification to both old and new email but I no longer have access to the old email.",
   "urgent", cat_account, "resolved",
   "Identity verified via your provided government ID. Email has been updated to your new address. Going forward you can use your personal email to login."),

  ("How to delete my account permanently",
   "I want to permanently delete my account and all my data. I cannot find this option anywhere in settings. Please guide me or do it for me if needed.",
   "low", cat_account, "resolved",
   "Account deletion option is under Settings > Privacy > Delete Account. Note: deletion is permanent and we cannot recover data. All your data will be deleted within 30 days per our retention policy. Let me know if you would like to proceed."),

  ("Profile picture not updating",
   "I uploaded a new profile picture but it still shows my old photo everywhere. I have tried uploading 3 times. The upload seems to succeed but nothing changes.",
   "low", cat_account, "resolved",
   "Profile picture CDN cache was not being invalidated after updates. Fixed — your new profile picture should appear everywhere now after a hard refresh."),

  ("Team member removed by mistake need to restore",
   "I accidentally removed a team member who should have stayed. Their account is deactivated and they cannot login. Can you restore their access?",
   "medium", cat_account, "resolved",
   "Team member account has been restored with their original role and permissions. They will receive an email notification that access has been reinstated."),

  ("Cannot see tickets created by former employee",
   "A colleague who left the company had created several tickets. After their account was deactivated these tickets disappeared from our view. We need access to this history.",
   "medium", cat_account, "resolved",
   "Tickets created by deactivated users are now visible. They were hidden by a filter. Tickets are still in the system — go to Filters and enable Show tickets from inactive users to see them."),

  ("Account timezone showing wrong time everywhere",
   "All timestamps in my account show the wrong time. They are 5.5 hours behind. My timezone is set to IST in settings but it looks like the system is using UTC.",
   "low", cat_account, "resolved",
   "Timezone display was correctly stored but not applied to timestamps in certain views. Fixed — all timestamps now display in your configured IST timezone."),

  ("Two accounts merged incorrectly",
   "I had two accounts and requested them to be merged. After the merge some of my tickets from the old account are missing and others are duplicated.",
   "medium", cat_account, "in_progress",
   None),

  ("API key for my account stopped working",
   "Our system uses an API key to authenticate with your service. The key stopped working yesterday with a 401 error. I have not changed anything. Key is still showing as active in settings.",
   "urgent", cat_account, "resolved",
   "API keys were invalidated during a security rotation last night. New keys are required. Please generate a new API key from Settings > API > New Key and update your system configuration."),

  ("Cannot set custom role permissions for team",
   "We need some team members to only view tickets without being able to comment or change status. The current roles (admin/agent/customer) do not cover this use case.",
   "low", cat_account, "open",
   None),

  ("Account suspended without notification",
   "My account was suddenly suspended and I cannot access anything. I did not receive any warning or explanation. I need access restored immediately as we use this for customer operations.",
   "urgent", cat_account, "resolved",
   "Account was automatically suspended due to a billing failure from an expired card. Card has been updated, payment processed, and account restored immediately. We apologize for the disruption — a notification should have been sent but was not due to a bug we have now fixed."),

  ("How to export all my data",
   "I want to export all my ticket data, comments, and account information. Is there a way to get a complete data export? I need this for compliance purposes.",
   "low", cat_account, "resolved",
   "Data export is available under Settings > Privacy > Export My Data. You will receive a download link via email within 24 hours containing all your tickets, comments, and profile data in JSON and CSV format."),

  ("Notification preferences reset after every login",
   "Every time I login my notification preferences are back to default. I have to re-configure which emails I want every single session. Very frustrating.",
   "medium", cat_account, "resolved",
   "Notification preferences were being saved to a session cookie instead of the database. Fixed — your preferences will now persist correctly across sessions."),

  ("Cannot grant admin access to another user",
   "I am the account owner and want to make another user an admin. When I change their role to admin and save, it reverts back to agent after a few seconds.",
   "medium", cat_account, "resolved",
   "A permissions validation bug was rejecting admin promotions if the account had more than 5 users. Fixed. Please try granting admin access again — it should save correctly now."),

  ("Usage statistics showing zero despite activity",
   "The usage statistics dashboard shows 0 for everything — tickets created, responses sent, resolution time. But we have been actively using the platform for 2 months.",
   "medium", cat_account, "resolved",
   "Usage statistics were not being calculated for accounts created before January 2026. Backfill job has been run for your account — all stats should now correctly reflect your 2 months of activity."),

  ("Webhook secret changed without my knowledge",
   "My webhook integrations broke overnight. When I checked the settings the webhook secret was different from what I set. I did not change it. Security concern.",
   "urgent", cat_account, "in_progress",
   None),

  ("Cannot leave a team I was added to",
   "I was added to a team by someone else but I do not want to be part of this team. There is no option to leave or remove myself from the team.",
   "low", cat_account, "resolved",
   "Leave team option has been added to the team settings page. You can now remove yourself from any team you are a member of."),

  ("Profile shows wrong job title after update",
   "I updated my job title in profile settings from Engineer to Senior Engineer. It saved successfully but still shows Engineer everywhere else in the app.",
   "low", cat_account, "resolved",
   "Job title was cached aggressively in the frontend. Cache cleared — your updated title should now appear everywhere immediately after save."),

  ("Old phone number still receiving account alerts",
   "I updated my phone number 3 weeks ago but all SMS alerts are still going to my old number. My old SIM is deactivated so I am missing all SMS notifications.",
   "medium", cat_account, "resolved",
   "Found that the SMS notification system was using a cached version of your old number. Cache cleared and SMS notifications now correctly routed to your new number."),


  # ══ CLUSTER E: Performance / Outage (20) ════════════════════════════════════

  ("Dashboard extremely slow to load",
   "The dashboard is taking over 30 seconds to load. It used to be instant. This started 3 days ago. I am on a 100mbps connection and other websites are fast.",
   "medium", cat_perf, "resolved",
   "Identified an unoptimized database query on the dashboard stats endpoint that was doing a full table scan. Query has been optimized with proper indexing. Dashboard should now load in under 2 seconds."),

  ("Complete service outage - cannot access anything",
   "Your entire service appears to be down. I cannot access the website, the API is timing out, and the mobile app shows a connection error. This is affecting our entire support team.",
   "urgent", cat_perf, "resolved",
   "We experienced a 47-minute outage due to a database failover issue. Services are fully restored as of 3:42 PM IST. We are conducting a full post-mortem and will publish an incident report within 24 hours. Sincerely sorry for the disruption."),

  ("Page not loading after network switch",
   "The web app gets stuck loading when I switch from WiFi to mobile data or back. I have to force close and reopen the browser to get it working again.",
   "low", cat_perf, "open",
   None),

  ("Reports taking 20 minutes to generate",
   "Generating any report takes 15-20 minutes and I receive a timeout error. Last month reports generated in seconds. We have not added significantly more tickets.",
   "medium", cat_perf, "resolved",
   "Report generation was running without date filters on the database query, causing it to process all historical data every time. Fixed with proper query optimization and report caching. Reports now generate in under 30 seconds."),

  ("API response times degraded to 10+ seconds",
   "Our integration monitors show your API average response time went from 200ms to over 10 seconds starting today. Intermittent timeouts are affecting our production system.",
   "urgent", cat_perf, "resolved",
   "Identified elevated load on our API servers due to a runaway process from one enterprise customer. Process terminated and auto-scaling triggered. API response times back to normal (<300ms). Added monitoring to prevent recurrence."),

  ("File downloads extremely slow",
   "Downloading any attachment or report from the platform is incredibly slow — 1MB files take several minutes. My internet connection is fast for everything else.",
   "medium", cat_perf, "resolved",
   "File downloads were being routed through our application server instead of directly from CDN due to a misconfigured URL. Fixed — downloads now served directly from CDN and should be very fast."),

  ("App battery drain on mobile is excessive",
   "Since the last update the mobile app is draining my phone battery much faster than before. My phone was at 100% after charging and the app drained it 40% in 2 hours while I only briefly used it.",
   "medium", cat_technical, "in_progress",
   None),

  ("Search results taking too long",
   "Searching for tickets takes about 15-20 seconds to return results. It used to be instant. I cannot work efficiently when every search takes that long.",
   "medium", cat_perf, "resolved",
   "Search index had become fragmented and was not using the optimized search backend. Rebuilt the search index and re-enabled ElasticSearch for all queries. Search should now return results in under 1 second."),

  ("High memory usage causing browser tab crashes",
   "After using the web app for about an hour the browser tab starts using 2GB+ of memory and eventually crashes. I lose all my unsaved work. This happens every day.",
   "medium", cat_technical, "resolved",
   "Memory leak identified in the real-time notifications component which was not cleaning up event listeners. Fixed in the latest release. Memory usage should remain stable through long sessions."),

  ("Images loading very slowly across the platform",
   "All images in the platform load very slowly. Profile pictures, attachments, everything. Takes 10-20 seconds for each image. Video content does not load at all.",
   "medium", cat_perf, "resolved",
   "Our CDN provider had a regional outage affecting the Mumbai edge node. Traffic has been rerouted to the Singapore node which is performing normally. Images should load at full speed now."),

  ("Real-time ticket updates not working",
   "Our team relies on real-time updates so we can see when tickets are updated by agents. The live updates stopped working and we now have to manually refresh to see changes.",
   "medium", cat_perf, "resolved",
   "WebSocket connection was being rejected by our load balancer configuration after a recent infrastructure change. Fixed the load balancer config to support persistent WebSocket connections. Real-time updates should work again."),

  ("Scheduled reports not arriving",
   "I set up daily and weekly report emails but have not received any for the past 2 weeks. The schedule shows as active in settings.",
   "medium", cat_perf, "resolved",
   "Scheduled email jobs were failing silently due to a missing email service API key after our infrastructure migration. Key has been restored and jobs are running again. Next scheduled report will arrive at the configured time."),

  ("Cannot load more than 100 tickets in list view",
   "My team has thousands of tickets but the list view only shows 100 and the Load More button does not work. Clicking it does nothing — no spinner, no additional tickets.",
   "medium", cat_technical, "resolved",
   "Pagination was hardcoded to a 100-record limit with a broken load-more implementation. Fixed to support proper cursor-based pagination. You can now load all tickets with proper pagination controls."),

  ("Intermittent 503 errors throughout the day",
   "We are seeing random 503 Service Unavailable errors multiple times throughout the day. Each one lasts about 30-60 seconds then resolves. Very disruptive to our team.",
   "urgent", cat_perf, "resolved",
   "503 errors were caused by our health check misconfiguration causing good instances to be marked unhealthy and removed from rotation. Fixed the health check thresholds. 503 errors should not recur."),

  ("Slow performance only during business hours",
   "The platform performs normally in evenings and weekends but slows significantly between 10am-6pm IST. Clearly a capacity issue during peak hours.",
   "medium", cat_perf, "in_progress",
   None),

  ("Data refresh taking too long after ticket updates",
   "After I update a ticket it takes 30+ seconds for the change to reflect in the ticket list. During that time the old data shows which is confusing.",
   "low", cat_perf, "resolved",
   "Cache invalidation after ticket updates was batched every 30 seconds. Changed to immediate invalidation on update. Changes should now reflect in the list within 1-2 seconds."),

  ("Video calls in platform not connecting",
   "We use the built-in video call feature for support sessions but calls fail to connect about 70% of the time. The other 30% connects but has terrible audio and video quality.",
   "medium", cat_technical, "in_progress",
   None),

  ("Bulk import of tickets failing at large numbers",
   "I am trying to import our historical tickets from the old system using the bulk import feature. Imports under 100 tickets work but anything over 500 times out and fails.",
   "medium", cat_technical, "resolved",
   "Bulk imports were running synchronously and hitting the request timeout. Converted to async background processing — large imports now run in the background and you receive an email when complete."),

  ("Widget on our website not loading",
   "We embedded your support widget on our website but it stopped loading last Tuesday. Our customers cannot raise tickets from the widget. Shows a blank space.",
   "urgent", cat_perf, "resolved",
   "The widget CDN URL changed after our infrastructure migration without proper redirect. Updated the embed code in your widget settings — please update the script on your website with the new embed code provided."),

  ("PDF attachments corrupt when downloaded",
   "Several customers have reported that PDF attachments they download from tickets are corrupt and cannot be opened. The files show as 0 bytes or fail to open in PDF reader.",
   "medium", cat_technical, "resolved",
   "Attachment storage was applying an incorrect content-encoding that corrupted binary files like PDFs. Fixed the encoding pipeline. New uploads work correctly. For existing corrupt files, please re-upload the originals."),


  # ══ CLUSTER F: Feature Requests (20) ════════════════════════════════════════

  ("Please add dark mode to the web dashboard",
   "The web dashboard is very bright and causes eye strain during long work sessions. Can you add a dark mode option? The mobile app already has dark mode but the web version does not.",
   "low", cat_general, "open",
   None),

  ("Need ability to add internal notes on tickets",
   "We need a way to add internal notes on tickets that are visible to agents only and not shown to customers. Currently all comments are visible to the customer which is problematic.",
   "low", cat_general, "in_progress",
   None),

  ("Request for ticket priority auto-suggestion",
   "It would be very helpful if the system automatically suggested a priority level when creating a ticket based on the content. Currently agents have to manually assess each ticket.",
   "low", cat_general, "open",
   None),

  ("Bulk reply to multiple tickets at once",
   "When there is a system-wide issue I need to reply to 50+ tickets with the same message. Currently I have to do it one by one which takes hours. Please add bulk reply functionality.",
   "low", cat_general, "open",
   None),

  ("Add keyboard shortcuts for common actions",
   "Power users like me would love keyboard shortcuts. For example N to create new ticket, R to reply, S to change status. This would significantly speed up our workflow.",
   "low", cat_general, "open",
   None),

  ("Integration with Slack for notifications",
   "We use Slack for all team communication. It would be very useful to receive ticket notifications in our Slack channel instead of having to check email or the dashboard constantly.",
   "low", cat_general, "in_progress",
   None),

  ("Ability to merge duplicate tickets",
   "We frequently get multiple customers reporting the same issue. We need a merge tickets feature to combine duplicates into one ticket while keeping all the conversations.",
   "low", cat_general, "open",
   None),

  ("Add SLA tracking and breach alerts",
   "We need SLA tracking to ensure tickets are resolved within promised timeframes. We need automated alerts when a ticket is approaching or has breached SLA.",
   "low", cat_general, "open",
   None),

  ("Customer satisfaction rating after resolution",
   "After a ticket is resolved can you add a CSAT survey so customers can rate their experience? This is standard in support tools and we need the data for performance reviews.",
   "low", cat_general, "open",
   None),

  ("Saved reply templates for common responses",
   "Our agents type the same responses repeatedly for common issues. We need a library of saved reply templates that agents can quickly insert instead of typing from scratch each time.",
   "low", cat_general, "open",
   None),

  ("Mobile app for agents to manage tickets",
   "Agents currently have no way to manage tickets from mobile. We need a proper agent mobile app or at least a mobile-optimized web view so agents can respond on the go.",
   "low", cat_general, "in_progress",
   None),

  ("Advanced filtering and custom ticket views",
   "The current filter options are very basic. We need advanced filters like assigned agent + status + date range combined, and the ability to save custom views for different team members.",
   "low", cat_general, "open",
   None),

  ("Ticket assignment round-robin automation",
   "Currently tickets are manually assigned to agents. We want automatic round-robin assignment so tickets are distributed evenly across the available agents without manual work.",
   "low", cat_general, "open",
   None),

  ("Add a public status page for system incidents",
   "When your service has an outage or degraded performance we have no way to check official status. Please add a public status page like statuspage.io so we can check without raising tickets.",
   "low", cat_general, "open",
   None),

  ("Custom fields on ticket creation form",
   "We need to collect specific information when customers create tickets — like account number, product version, operating system. Can you add customizable fields to the ticket form?",
   "low", cat_general, "open",
   None),

  ("Email-to-ticket conversion",
   "Can customers send an email to a support address and have it automatically create a ticket? We would prefer customers to email us rather than use a web form.",
   "low", cat_general, "in_progress",
   None),

  ("Add Tags or Labels to tickets",
   "We need to be able to tag tickets with labels like bug, feature-request, escalated, VIP-customer etc for better organisation and filtering. Currently categories are too limited.",
   "low", cat_general, "open",
   None),

  ("Reporting on agent performance metrics",
   "We need detailed reports on individual agent performance — tickets resolved per day, average first response time, CSAT scores per agent. Current reporting is too high-level.",
   "low", cat_general, "open",
   None),

  ("Chatbot for first-line support",
   "Can you add a configurable chatbot that can answer common questions automatically before escalating to a human agent? This would reduce ticket volume significantly.",
   "low", cat_general, "open",
   None),

  ("Multi-language support for the platform",
   "Our customers span India and Southeast Asia and many are not comfortable with English. We need the platform to support Hindi, Tamil, Telugu, and Bahasa Indonesia at minimum.",
   "low", cat_general, "open",
   None),
]

# ── Create tickets ──────────────────────────────────────────────────────────────
print(f"\nCreating {len(TICKETS)} tickets...")

created_tickets = []
for i, (title, desc, priority, category, status, resolution) in enumerate(TICKETS):
    # Spread creation dates over the past 90 days for realism
    days_ago = random.randint(0, 90)
    created_at = datetime.utcnow() - timedelta(days=days_ago)
    updated_at = created_at + timedelta(hours=random.randint(1, 48))

    customer = random.choice(customers)
    agent    = random.choice(agents) if status in ("in_progress", "resolved") else None

    ticket = Ticket(
        title=title,
        description=desc,
        priority=priority,
        category_id=category.id,
        customer_id=customer.id,
        agent_id=agent.id if agent else None,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(ticket)
    db.flush()  # get ticket.id without committing

    # Add resolution comment if ticket is resolved
    if resolution and status == "resolved":
        comment = Comment(
            content=resolution,
            ticket_id=ticket.id,
            user_id=random.choice(agents).id,
            is_ai_generated=False,
            created_at=updated_at,
        )
        db.add(comment)

    created_tickets.append(ticket)
    if (i + 1) % 20 == 0:
        print(f"  ... {i+1}/{len(TICKETS)} tickets created")

db.commit()
print(f"\n✅ Done! Created {len(TICKETS)} tickets across 6 semantic clusters.")
print("""
Clusters:
  A. Login / Auth       → tickets should cluster together semantically
  B. Payment / Billing  → billing issues cluster
  C. Technical / Bugs   → app bug cluster
  D. Account Mgmt       → account settings cluster
  E. Performance        → slow/outage cluster
  F. Feature Requests   → wishlist cluster

Demo accounts (password: password123):
  Agents:    som@support.com / neha@support.com
  Customers: rahul@example.com / priya@example.com / amit@example.com
             sneha@example.com / vikram@example.com
""")
db.close()
