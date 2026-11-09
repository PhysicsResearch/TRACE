"""
Product names in the log files.

The code works with its own device words ('Lung Phantom', 'Motion Platform'); the log files written from now on name
the products: '# Device: DYNAMIQ' (the lung phantom) and '# Device: KINETIQ' (the motion platform).  Readers accept
both, old and new logs:

    canonical_device('KINETIQ') == canonical_device('Motion Platform') == 'Motion Platform'
    canonical_device('DYNAMIQ') == canonical_device('Lung Phantom')    == 'Lung Phantom'
"""
SOFTWARE_NAME = "LogIQ"
PHANTOM = "Lung Phantom"            # the code's device words (combo items, checks)
PLATFORM = "Motion Platform"
PHANTOM_PRODUCT = "DYNAMIQ"
PLATFORM_PRODUCT = "KINETIQ"

_LABELS = {PHANTOM: PHANTOM_PRODUCT, PLATFORM: PLATFORM_PRODUCT}


def device_label(device):
    """Device word of the code -> the name written in a log file ('Motion Platform' -> 'KINETIQ')."""
    if not isinstance(device, str):
        return device
    return _LABELS.get(device.strip(), device)


def canonical_device(text):
    """Device as written in any log (new product name, old device word, older spellings) -> the code's word.
    Unknown text is returned unchanged; empty -> None."""
    if not isinstance(text, str) or not text.strip():
        return None
    t = text.strip()
    low = t.lower()
    if PLATFORM_PRODUCT.lower() in low or 'platform' in low:
        return PLATFORM
    if PHANTOM_PRODUCT.lower() in low or 'phantom' in low or low.startswith('lung'):
        return PHANTOM
    return t
