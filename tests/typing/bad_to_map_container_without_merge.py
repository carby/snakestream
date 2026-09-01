from collections import OrderedDict

from snakestream.collectors import to_map

# There is no to_map(key_mapper, value_mapper, map_supplier) form: Java has no
# such overload, and the exclusion is enforced by the declared surface rather
# than by a runtime raise, since "a merge function" and "a mapping type" are
# both callables of the right shape.
to_map(len, str.upper, map_supplier=OrderedDict)
