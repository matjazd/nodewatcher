from web.registry import registration
from web.registry.cgm import routers as cgm_routers

# Registered platform modules
PLATFORM_REGISTRY = {}

class ValidationError(Exception):
  pass

class PlatformConfiguration(object):
  """
  A flexible in-memory platform configuration store that is used
  by modules to make modifications and perform configuration. The
  default implementation is empty as this is platform-specific.
  """
  pass

class PlatformBase(object):
  """
  An abstract base class for all platform implementations.
  """
  config_class = PlatformConfiguration
  
  def __init__(self):
    """
    Class constructor.
    """
    self._modules = []
    self._packages = []
    self._routers = {}
  
  def generate(self, node):
    """
    Generates a concrete configuration for this platform.
    """
    cfg = self.config_class()
    
    # Execute the module chain in order
    for _, module, router in sorted(self._modules):
      if router is None or router == node.config.core.general().router:
        module(node, cfg)
    
    # Process packages
    for name, cfgclass, package in self._packages:
      pkgcfg = node.config.core.packages(onlyclass = cfgclass)
      if [x for x in pkgcfg if x.enabled]:
        package(node, pkgcfg, cfg)
        self.install_optional_package(name)
    
    return cfg
  
  def format(self, cfg):
    raise NotImplementedError

  def build(self):
    raise NotImplementedError
  
  def install_optional_package(self, name):
    raise NotImplementedError
  
  def defer_format_build(self, node, cfg):
    # TODO Defer formatting and build process via Celery
    
    # TODO Don't forget to add proper Celery routing so this doesn't
    #      get routed to the workers for generating graphs!
    pass
  
  def register_module(self, order, module, router = None):
    """
    Registers a new platform module.
    
    @param order: Call order
    @param module: Module implementation function
    @param router: Optional router identifier
    """
    if [x for x in self._modules if x[1] == module]:
      return
    
    self._modules.append((order, module, router))
  
  def register_package(self, name, config, package):
    """
    Registers a new platform package.
    
    @param name: Platform-dependent package name
    @param config: Configuration class
    @param package: Package implementation function
    """
    if [x for x in self._packages if x[2] == package]:
      return
    
    self._packages.append((name, config, package))
  
  def register_router(self, router):
    """
    Registers a new router with this platform.
    
    @param router: A subclass of RouterBase
    """
    if not issubclass(router, cgm_routers.RouterBase):
      raise TypeError("Router descriptor must be a subclass of RouterBase!")
    
    self._routers[router.identifier] = router
    router.register(self)
  
  def get_router(self, router):
    """
    Returns a router descriptor.
    
    @param router: Unique router identifier
    """
    return self._routers[router]

def register_platform(enum, text, platform):
  """
  Registers a new platform with the Configuration Generation Modules
  system.
  """
  if not isinstance(platform, PlatformBase):
    raise TypeError, "Platform formatter/builder implementation must be a PlatformBase instance!"
  
  if enum in PLATFORM_REGISTRY:
    raise ValueError, "Platform '{0}' is already registered!".format(enum)
  
  PLATFORM_REGISTRY[enum] = platform
  platform.name = enum
  
  # Register the choice in configuration registry
  registration.point("node.config").register_choice("core.general#platform", enum, text)

def get_platform(platform):
  """
  Returns the given platform implementation.
  """
  try:
    return PLATFORM_REGISTRY[platform]
  except KeyError:
    raise KeyError, "Platform '{0}' does not exist!".format(platform)

def register_platform_module(platform, order, router = None):
  """
  Registers a new platform module.
  """
  def wrapper(f):
    get_platform(platform).register_module(order, f, router = router)
    return f
  
  return wrapper

def register_platform_package(platform, name, cfgclass):
  """
  Registers a new platform package.
  """
  def wrapper(f):
    get_platform(platform).register_package(name, cfgclass, f)
    return f
  
  return wrapper

def register_router(platform, router):
  """
  Registers a new router.
  """
  get_platform(platform).register_router(router)

