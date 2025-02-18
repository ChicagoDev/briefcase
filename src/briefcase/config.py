import copy
import keyword
import re
from types import SimpleNamespace

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from briefcase.platforms import get_output_formats, get_platforms

from .exceptions import BriefcaseConfigError

# PEP508 provides a basic restriction on naming
PEP508_NAME_RE = re.compile(
    r'^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$',
    re.IGNORECASE
)

# Javascript reserved keywords:
# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Lexical_grammar#reserved_keywords_as_of_ecmascript_2015
JAVASCRIPT_RESERVED_WORDS = {
    'break',
    'case',
    'catch',
    'class',
    'const',
    'continue',
    'debugger',
    'default',
    'delete',
    'do',
    'else',
    'export',
    'extends',
    'finally',
    'for',
    'function',
    'if',
    'import',
    'in',
    'instanceof',
    'new',
    'return',
    'super',
    'switch',
    'this',
    'throw',
    'try',
    'typeof',
    'var',
    'void',
    'while',
    'with',
    'yield',
}

# Java reserved keywords
# https://en.wikipedia.org/wiki/List_of_Java_keywords
JAVA_RESERVED_WORDS = {
    # Keywords
    'abstract',
    'assert',
    'boolean',
    'break',
    'byte',
    'case',
    'catch',
    'char',
    'class',
    'const',
    'continue',
    'default',
    'do',
    'double',
    'else',
    'enum',
    'extends',
    'final',
    'finally',
    'float',
    'for',
    'goto',
    'if',
    'implements',
    'import',
    'instanceof',
    'int',
    'interface',
    'long',
    'native',
    'new',
    'package',
    'private',
    'protected',
    'public',
    'return',
    'short',
    'static',
    'super',
    'switch',
    'synchronized',
    'this',
    'throw',
    'throws',
    'transient',
    'try',
    'void',
    'volatile',
    'while',

    # Reserved Identifiers
    'exports',
    'module',
    'non-sealed',
    'open',
    'opens',
    'permits',
    'provides',
    'record',
    'requires',
    'sealed',
    'to',
    'transitive',
    'uses',
    'var',
    'with',
    'yield',

    # Reserved Literals
    'true',
    'false',
    'null',

    # Unused, but reserved.
    'strictfp',
}


# Names that are illegal as Windows filenames
# https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file
WINDOWS_RESERVED_WORDS = {
    'con',
    'prn',
    'aux',
    'nul',
    'com1',
    'com2',
    'com3',
    'com4',
    'com5',
    'com6',
    'com7',
    'com8',
    'com9',
    'com0',
    'lpt1',
    'lpt2',
    'lpt3',
    'lpt4',
    'lpt5',
    'lpt6',
    'lpt7',
    'lpt8',
    'lpt9',
    'lpt0',
}

NON_PYTHON_RESERVED_WORDS = set.union(
    JAVASCRIPT_RESERVED_WORDS,
    JAVA_RESERVED_WORDS,
    WINDOWS_RESERVED_WORDS,
)


def is_valid_pep508_name(app_name):
    "Determine if the name is valid by PEP508 rules"
    return PEP508_NAME_RE.match(app_name)


def is_reserved_keyword(app_name):
    "Determine if the name is a reserved keyword"
    return keyword.iskeyword(app_name.lower()) or app_name.lower() in NON_PYTHON_RESERVED_WORDS


def is_valid_app_name(app_name):
    if not is_reserved_keyword(app_name) and is_valid_pep508_name(app_name):
        return True
    return False


VALID_BUNDLE_RE = re.compile(r'[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$')


def is_valid_bundle_identifier(bundle):
    # Ensure the bundle identifier follows the basi
    if not VALID_BUNDLE_RE.match(bundle):
        return False

    for part in bundle.split('.'):
        # *Some* 2-letter country codes are valid identifiers,
        # even though they're reserved words; see:
        #    https://www.oracle.com/java/technologies/javase/codeconventions-namingconventions.html
        # `.do` *should* be on this list, but as of Apr 2022, `.do` breaks
        # the Android build tooling.
        if is_reserved_keyword(part) and part not in {'in', 'is'}:
            return False

    return True


# This is the canonical definition from PEP440, modified to include named groups
PEP440_CANONICAL_VERSION_PATTERN_RE = re.compile(
    r'^((?P<epoch>[1-9][0-9]*)!)?'
    r'(?P<release>(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*)'
    r'((?P<pre_tag>a|b|rc)(?P<pre_value>0|[1-9][0-9]*))?'
    r'(\.post(?P<post>0|[1-9][0-9]*))?'
    r'(\.dev(?P<dev>0|[1-9][0-9]*))?$'
)


def is_pep440_canonical_version(version):
    """
    Determine if the string describes a valid PEP440 canonical version specifier.

    This implementation comes directly from PEP440 itself.

    :returns: True if the version string is valid; false otherwise.
    """
    return PEP440_CANONICAL_VERSION_PATTERN_RE.match(version) is not None


def parsed_version(version):
    """
    Return a parsed version string

    :param version: The parsed version string
    """
    groupdict = PEP440_CANONICAL_VERSION_PATTERN_RE.match(version).groupdict()

    # Convert dot separated string of integers to tuple of integers
    groupdict['release'] = tuple(int(p) for p in groupdict.pop('release').split('.'))

    # Convert strings to values
    for key in ('epoch', 'pre_value', 'post', 'dev'):
        try:
            groupdict[key] = int(groupdict[key])
        except TypeError:
            pass

    tag = groupdict.pop('pre_tag')
    value = groupdict.pop('pre_value')
    if tag is not None:
        groupdict['pre'] = (tag, value)
    else:
        groupdict['pre'] = None

    return SimpleNamespace(**groupdict)


class BaseConfig:
    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)


class GlobalConfig(BaseConfig):
    def __init__(
        self,
        project_name,
        version,
        bundle,
        url=None,
        author=None,
        author_email=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.project_name = project_name
        self.version = version
        self.bundle = bundle
        self.url = url
        self.author = author
        self.author_email = author_email

        # Version number is PEP440 compliant:
        if not is_pep440_canonical_version(self.version):
            raise BriefcaseConfigError(
                "Version number ({self.version}) is not valid.\n\n"
                "Version numbers must be PEP440 compliant; "
                "see https://www.python.org/dev/peps/pep-0440/ for details.".format(
                    self=self
                )
            )

    def __repr__(self):
        return "<{self.project_name} v{self.version} GlobalConfig>".format(self=self)


class AppConfig(BaseConfig):
    def __init__(
        self,
        app_name,
        version,
        bundle,
        description,
        sources,
        formal_name=None,
        url=None,
        author=None,
        author_email=None,
        requires=None,
        icon=None,
        splash=None,
        document_type=None,
        template=None,
        template_branch=None,
        supported=True,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.app_name = app_name
        self.version = version
        self.bundle = bundle
        self.description = description
        self.sources = sources
        self.formal_name = app_name if formal_name is None else formal_name
        self.url = url
        self.author = author
        self.author_email = author_email
        self.requires = requires
        self.icon = icon
        self.splash = splash
        self.document_types = {} if document_type is None else document_type
        self.template = template
        self.template_branch = template_branch
        self.supported = supported

        if not is_valid_app_name(self.app_name):
            raise BriefcaseConfigError(
                f"{self.app_name!r} is not a valid app name.\n\n"
                "App names must not be reserved keywords such as 'and', 'for' and 'while'.\n"
                "They must also be PEP508 compliant (i.e., they can only include letters,\n"
                "numbers, '-' and '_'; must start with a letter; and cannot end with '-' or '_')."
            )

        if not is_valid_bundle_identifier(self.bundle):
            raise BriefcaseConfigError(
                f"{self.bundle!r} is not a valid bundle identifier.\n\n"
                "The bundle should be a reversed domain name. It must contain at least 2\n"
                "dot-separated sections; each section may only include letters, numbers,\n"
                "and hyphens; and each section may not contain any reserved words (like\n"
                "'switch', or 'while')."
            )

        # Version number is PEP440 compliant:
        if not is_pep440_canonical_version(self.version):
            raise BriefcaseConfigError(
                f"Version number for {self.app_name!r} ({self.version}) is not valid.\n\n"
                "Version numbers must be PEP440 compliant; "
                "see https://www.python.org/dev/peps/pep-0440/ for details."
            )

        # Sources list doesn't include any duplicates
        source_modules = {source.rsplit('/', 1)[-1] for source in self.sources}
        if len(self.sources) != len(source_modules):
            raise BriefcaseConfigError(
                f"The `sources` list for {self.app_name!r} contains duplicated "
                "package names."
            )

        # There is, at least, a source for the app module
        if self.module_name not in source_modules:
            raise BriefcaseConfigError(
                f"The `sources` list for {self.app_name!r} does not include a "
                f"package named {self.module_name!r}."
            )

    def __repr__(self):
        return f"<{self.bundle}.{self.app_name} v{self.version} AppConfig>"

    @property
    def module_name(self):
        """
        The module name for the app.

        This is derived from the name, but:
        * all `-` have been replaced with `_`.
        """
        return self.app_name.replace('-', '_')

    @property
    def package_name(self):
        """
        The bundle name of the app, with `-` replaced with `_` to create
        something that can be used a namespace identifier on Python or Java,
        similar to `module_name`.
        """
        return self.bundle.replace('-', '_')

    @property
    def PYTHONPATH(self):
        "The PYTHONPATH modifications needed to run this app."
        paths = []
        for source in self.sources:
            path = source.rsplit('/', 1)[0]
            if path not in paths:
                paths.append(path)
        return paths


def merge_config(config, data):
    """
    Merge a new set of configuration requirements into a base configuration.

    :param config: the base configuration to update. This configuration
        is modified in-situ.
    :param data: The new configuration data to merge into the configuration.
    """
    for option in ['requires', 'sources']:
        value = data.pop(option, [])

        if value:
            config.setdefault(option, []).extend(value)

    config.update(data)


def parse_config(config_file, platform, output_format):
    """
    Parse the briefcase section of the pyproject.toml configuration file.

    This method only does basic structural parsing of the TOML, looking for,
    at a minimum, a ``[tool.briefcase.app.<appname>]`` section declaring the
    existence of a single app. It will also search for:

      * ``[tool.briefcase]`` - global briefcase settings
      * ``[tool.briefcase.app.<appname>]`` - settings specific to the app
      * ``[tool.briefcase.app.<appname>.<platform>]`` - settings specific to
        the platform
      * ``[tool.briefcase.app.<appname>.<platform>.<format>]`` - settings
        specific to the output format

    A configuration can define multiple apps; the final output is the merged
    content of the global, app, platform and output format settings
    for each app, with output format definitions taking precendence over
    platform, over app-level, over global. The final result is a single
    (mostly) flat dictionary for each app.

    :param config_file: A file-like object containing TOML to be parsed.
    :param platform: The platform being targetted
    :param output_format: The output format
    :returns: A dictionary of configuration data. The top level dictionary is
        keyed by the names of the apps that are declared; each value is
        itself the configuration data merged from global, app, platform and
        format definitions.
    """
    try:
        pyproject = tomllib.load(config_file)

        global_config = pyproject['tool']['briefcase']
    except tomllib.TOMLDecodeError as e:
        raise BriefcaseConfigError('Invalid pyproject.toml: {e}'.format(e=e))
    except KeyError:
        raise BriefcaseConfigError('No tool.briefcase section in pyproject.toml')

    # For consistent results, sort the platforms and formats
    all_platforms = sorted(get_platforms().keys())
    all_formats = sorted(get_output_formats(platform).keys())

    try:
        all_apps = global_config.pop('app')
    except KeyError:
        raise BriefcaseConfigError('No Briefcase apps defined in pyproject.toml')

    # Build the flat configuration for each app,
    # based on the requested platform and output format
    app_configs = {}
    for app_name, app_data in all_apps.items():
        # At this point, the base configuration will contain a section
        # for each configured platform. Iterate over all the known platforms,
        # and remove these platform configurations. Keep a copy of the platform
        # configuration if it matches the requested platform, and merge it
        # into the app's configuration
        platform_data = None
        for p in all_platforms:
            try:
                platform_block = app_data.pop(p)

                if p == platform:
                    # If the platform matches the requested format, preserve
                    # it for later use.
                    platform_data = platform_block
                    merge_config(platform_data, platform_data)

                    # The platform configuration will contain a section
                    # for each configured output format. Iterate over all
                    # the output format of the platform, and remove these
                    # output format configurations. Keep a copy of the output
                    # format configuration if it matches the requested output
                    # format, and merge it into the platform's configuration.
                    format_data = None
                    for f in all_formats:
                        try:
                            format_block = platform_data.pop(f)

                            if f == output_format:
                                # If the output format matches the requested
                                # one, preserve it.
                                format_data = format_block

                        except KeyError:
                            pass

                    # If we found a specific configuration for the requested
                    # output format, add it to the platform configuration,
                    # overwriting any platform-level settings with format-level
                    # values.
                    if format_data:
                        merge_config(platform_data, format_data)

            except KeyError:
                pass

        # Now construct the final configuration.
        # First, convert the requirement definition at the global level
        merge_config(global_config, global_config)

        # The app's config starts as a copy of the base briefcase configuration.
        config = copy.deepcopy(global_config)

        # The app name is both the key, and a property of the configuration
        config['app_name'] = app_name

        # Merge the app-specific requirements
        merge_config(config, app_data)

        # If there is platform-specific configuration, merge the requirements,
        # then overwrite the platform-specific values.
        # This will already include any format-specific configuration.
        if platform_data:
            merge_config(config, platform_data)

        # Construct a configuration object, and add it to the list
        # of configurations that are being handled.
        app_configs[app_name] = config

    return global_config, app_configs
