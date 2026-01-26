# Ownership & Permissions System

## Overview
Added ownership tracking and edit permissions to RealAgent. Each listing now has an owner (creator) and only the owner or admin can edit it.

## Database Changes

### New Columns Added to `listings` table:
- `created_by` TEXT - Username of the agent who created the listing
- `updated_by` TEXT - Username of the last agent who edited the listing

### Migration
The system automatically adds these columns to existing databases. Old listings default to "admin" as owner.

## Setting Your Username

### Option 1: Environment Variable (Recommended)
```bash
export REALAGENT_USER="john"
# or
export AGENT_NAME="john"
```

### Option 2: Hostname (Automatic)
If no environment variable is set, the system uses your computer's hostname.

## How It Works

### Creating Listings
When an agent scrapes a new listing:
- `created_by` = current agent's username
- `updated_by` = current agent's username

### Editing Listings
When an agent tries to edit a listing:
1. System checks if user is "admin" → ✅ Allow
2. System checks if user is the owner → ✅ Allow  
3. Otherwise → ❌ Deny with message: "This listing belongs to {owner}"

### Permission Check Function
```python
from Helper.database import can_edit_listing

permission = can_edit_listing(listing_id, user="john")

if permission['can_edit']:
    # Allow edit
else:
    print(permission['reason'])  # "This listing belongs to maria"
```

## Dashboard Integration

### API Changes
- `PUT /api/listing/<id>` now checks permissions before allowing updates
- Returns 403 Forbidden if user doesn't have permission
- Response includes owner information

### UI Changes
- Listing cards show owner: "👤 john"
- Permission denied errors display owner name
- Console shows permission checks

## Multi-Agent Workflow

### Scenario 1: Different Listings (No Conflicts)
```
Agent John scrapes listing 12345 → created_by: john
Agent Maria scrapes listing 67890 → created_by: maria
✅ No conflicts - different listings
```

### Scenario 2: Editing Own Listing
```
Agent John edits listing 12345 (owner: john)
✅ Allowed - John owns this listing
```

### Scenario 3: Editing Someone Else's Listing
```
Agent Maria tries to edit listing 12345 (owner: john)
❌ Denied - "This listing belongs to john"
```

### Scenario 4: Admin Override
```
Admin edits any listing
✅ Always allowed - Admin has full access
```

## Testing

### Test as Different Users
```bash
# Terminal 1 - Agent John
export REALAGENT_USER="john"
python Dashboard.py

# Terminal 2 - Agent Maria  
export REALAGENT_USER="maria"
python Dashboard.py 5001  # Different port
```

### Test Permission Denial
1. Agent John creates a listing
2. Agent Maria tries to edit it
3. Should see: "🚫 PERMISSION DENIED" in console
4. Dashboard shows error: "This listing belongs to john"

## Admin Access

To have full access to all listings:
```bash
export REALAGENT_USER="admin"
```

Or set your hostname to "admin".

## Backward Compatibility

✅ Existing listings work fine - default to "admin" owner
✅ No breaking changes - system works without environment variables
✅ Automatic migration - columns added on first run

## Future Enhancements

Possible additions:
- User roles (admin, editor, viewer)
- Team/group ownership
- Transfer ownership feature
- Audit log of who edited what
- Lock listings while being edited
