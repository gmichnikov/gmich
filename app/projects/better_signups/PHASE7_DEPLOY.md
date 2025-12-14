# Phase 7 Deployment - Quick Guide

## What Was Done

Phase 7 implements automatic expiration of pending confirmations after 24 hours:
- Real-time check when users view lists
- Background job via Heroku Scheduler (runs every 10 minutes)
- Automatic cascade to next person on waitlist

## How to Deploy

### 1. Commit & Push

```bash
git add app/projects/better_signups/
git commit -m "Phase 7: Expiration & Background Job"
git push heroku main
```

### 2. Set Up Heroku Scheduler

```bash
# Add scheduler (if you haven't already)
heroku addons:create scheduler:standard
```

Then in Heroku Dashboard:
1. Go to your app → Resources tab
2. Click "Heroku Scheduler" 
3. Click "Create job"
4. Configure:
   - **Command**: `flask process-waitlist-expirations`
   - **Frequency**: Every 10 minutes
   - **Dyno size**: Standard-1X
5. Save, then click "Run job now" to test

### 3. Verify It Works

```bash
# Watch logs
heroku logs --tail

# Should see: "No expired pending confirmations found"
# (or a count if any exist)
```

## That's It!

The expiration system will now:
- Check for expirations when anyone views a list (immediate)
- Check every 10 minutes via background job (backup)
- Delete expired signups and offer spot to next person

## Testing (Optional)

```bash
# Run from project root:
cd /Users/greg/projects/gmich
python -m app.projects.better_signups.test_expiration
```

## Troubleshooting

**Job not running?**
- Verify command is exactly: `flask process-waitlist-expirations`
- Check logs: `heroku logs --tail`

**Expirations not working?**
- Make sure signups have `status = 'pending_confirmation'`
- Check they're > 24 hours old

---

**Next**: Phase 8 will add email notifications to the cascade flow.

