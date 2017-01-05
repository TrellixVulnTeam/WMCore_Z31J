"""
Use this for only unit test
"""

class EmulatorHelper(object):
    """
    Works as global value for the emulator switch.
    WARNNING: This is not multi thread safe.
    """
    #DO not change default values
    PhEDEx = None
    ReqMgr = None

    @staticmethod
    def getEmulatorClass(clsName, *args):

        if clsName == 'PhEDEx':
            from WMQuality.Emulators.PhEDExClient.PhEDEx \
                import PhEDEx as PhEDExEmulator
            return PhEDExEmulator

        if clsName == 'ReqMgr':
            from WMQuality.Emulators.ReqMgrClient.ReqMgr \
                import ReqMgr as ReqMgrEmulator
            return ReqMgrEmulator

    @staticmethod
    def setEmulators(phedex=False, dbs=False, siteDB=False, requestMgr=False):
        if dbs or siteDB:
            raise NotImplementedError("There are no DBS or SiteDB emulators anymore. Use the mock-based emulators.")
        EmulatorHelper.PhEDEx = phedex
        EmulatorHelper.ReqMgr = requestMgr

    @staticmethod
    def resetEmulators():
        EmulatorHelper.PhEDEx = None
        EmulatorHelper.ReqMgr = None

    @staticmethod
    def getClass(wrappedClass, *args):
        """
        if emulator flag is set return emulator class
        otherwise return original class.
        if emulator flag is not initialized
            and EMULATOR_CONFIG environment variable is set,
        r
        """
        emFlag = getattr(EmulatorHelper, wrappedClass.__name__)
        if emFlag:
            return EmulatorHelper.getEmulatorClass(wrappedClass.__name__, *args)
        elif emFlag == None:
            try:
                from WMQuality.Emulators import emulatorSwitch
            except ImportError:
                # if emulatorSwitch class is not imported don't use
                # emulator
                setattr(EmulatorHelper, wrappedClass.__name__, False)
            else:
                envFlag = emulatorSwitch(wrappedClass.__name__)
                setattr(EmulatorHelper, wrappedClass.__name__, envFlag)
                if envFlag:
                    return EmulatorHelper.getEmulatorClass(wrappedClass.__name__, *args)
        # if emulator flag is False, return original class
        return wrappedClass

def emulatorHook(cls):
    """
    This is used as decorator to switch between Emulator and real Class
    on instance creation.
    """
    class EmulatorWrapper:
        def __init__(self, *args, **kwargs):
            aClass = EmulatorHelper.getClass(cls, *args)
            self.wrapped = aClass(*args, **kwargs)
            self.__class__.__name__ = self.wrapped.__class__.__name__

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    return EmulatorWrapper
