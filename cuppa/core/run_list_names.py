#          Copyright Jamie Allsop 2026-2026
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   Coerce cuppa.run() list entries to registry names
#-------------------------------------------------------------------------------

"""Turn ``cuppa.run`` dependency/profile list entries into registry names.

Preferred kwargs: ``import_dependencies`` / ``auto_enable_dependencies`` (and the
profile twins). Legacy ``dependencies`` / ``default_dependencies`` remain aliases.

Strings pass through. Factories must expose callable ``name()`` returning a
non-empty string registry key.
"""

import SCons.Errors

from cuppa.utility.types import is_string


def coalesce_aliased_run_list( preferred, legacy, preferred_name, legacy_name ):
    """Pick one list from preferred and legacy kwargs (``None`` means omitted).

    Passing both with unequal values is a StopError. Empty lists are valid.
    """
    preferred_set = preferred is not None
    legacy_set = legacy is not None
    if preferred_set and legacy_set:
        if preferred != legacy:
            raise SCons.Errors.StopError(
                    "cuppa.run: pass only one of {}= or {}= (legacy alias); "
                    "got unequal lists".format( preferred_name, legacy_name )
            )
        return preferred
    if preferred_set:
        return preferred
    if legacy_set:
        return legacy
    return []


def registry_name_from_run_entry( value, list_label='import_dependencies' ):
    """Return the registry name for one ``cuppa.run`` list entry.

    Raises ``SCons.Errors.StopError`` when a non-string value has no usable ``name()``.
    """
    if is_string( value ):
        return value

    name_attr = getattr( value, 'name', None )
    if name_attr is None:
        raise SCons.Errors.StopError(
                "cuppa.run {} entry {!r} has no name(); pass a string registry "
                "name or a dependency/profile factory that implements name()".format(
                        list_label, value
                )
        )

    try:
        if callable( name_attr ):
            resolved = name_attr()
        else:
            resolved = name_attr
    except Exception as error:
        raise SCons.Errors.StopError(
                "cuppa.run {} entry {!r} name() failed: {}".format(
                        list_label, value, error
                )
        )

    if not is_string( resolved ) or not resolved:
        raise SCons.Errors.StopError(
                "cuppa.run {} entry {!r} name() must return a non-empty string "
                "(got {!r})".format( list_label, value, resolved )
        )
    return resolved


def normalise_with_defaults( values, default_values, list_label ):
    """Normalise import/registration + auto-enable name lists for ``cuppa.run``.

    * ``default_values`` may mix strings and factories; factories become names for
      auto-enable and are also merged into the registration list when not already present.
    * ``values`` (import list) may be a deprecated dict of name→factory.

    Returns ``(registration_values, default_names, warning_or_None)``.
    """
    import six

    warning = None
    if isinstance( values, dict ):
        warning = (
                "Dictionary passed for {}, this approach has been deprecated, "
                "please use a list instead".format( list_label )
        )
        values = [ v for v in six.itervalues( values ) ]

    registration = list( values ) if values else []
    default_names = []
    seen_registration_ids = {
            id( entry ) for entry in registration if not is_string( entry )
    }

    for entry in ( default_values or [] ):
        if is_string( entry ):
            default_names.append( entry )
            continue
        default_names.append( registry_name_from_run_entry( entry, list_label ) )
        entry_id = id( entry )
        if entry_id not in seen_registration_ids:
            registration.append( entry )
            seen_registration_ids.add( entry_id )

    return registration, default_names, warning
