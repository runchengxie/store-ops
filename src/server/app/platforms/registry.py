"""Explicit allowlist; adding a platform requires a real adapter implementation."""
from app.platforms.emag.adapter import EmagAdapter

_ADAPTERS={'emag':EmagAdapter()}


def descriptors():
    return [a.descriptor for a in _ADAPTERS.values()]


def get_adapter(platform_id):
    try:
        return _ADAPTERS[platform_id]
    except (KeyError,TypeError):
        raise ValueError('Platform is not enabled') from None


def require_capability(platform_id,key):
    adapter=get_adapter(platform_id)
    capability=next((c for c in adapter.descriptor.capabilities if c.key==key),None)
    if capability is None or capability.status!='supported':
        raise ValueError('Capability is unsupported or unverified')
    return capability


def stores():
    rows=[]
    for adapter in _ADAPTERS.values():
        rows.extend(adapter.stores())
    return rows


def overview(store_id):
    # Existing IDs remain opaque. Reject ambiguity rather than silently pick an account.
    matches=[r for r in stores() if r['store_id']==store_id]
    if len(matches)!=1:
        raise FileNotFoundError('Store is missing or ambiguous')
    adapter=get_adapter(matches[0]['platform'])
    require_capability(adapter.descriptor.platform_id,'overview')
    return adapter.overview(store_id)
