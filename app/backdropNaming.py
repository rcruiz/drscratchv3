class BackdropNaming:
    """
    This class allows you to analyze the bad smell consisting of not
    assigning a descriptive name to the backdrops of the project that
    is being analyzed. Thus it allows to recover in its attributes
    the number and the list of names assigned by defects, when we
    instantiate an object of this class. Hence, it keeps track of
    how often backdrops default names (like Backdrop1, Backdrop2...)
    are used within a Scratch project.
    """

    def __init__(self):
        self.total_default = 0
        self.list_default = []
        self.default_names = ["backdrop", "fondo", "fons", "atzeko oihala"]

    def finalize(self):
        """
        Return the default backdrop names found in the Scratch project.
        Take the value of attribute self.total_default and retrieve the
        default names of the class attribute self.list_default.

        :return result: String with names and number of default backdrop.
        """
        result = ""
       
        result += ("%d default backdrop names found:\n" % self.total_default)
        for name in self.list_default:
            result += name
            result += "\n"

        return result

    def analyze(self, json_project):
        """ Search of default backdrop names.

        With an iterator over the (key, value) items of json_project,
        find all default backdrop naming related to the Scratch project.
        Save into a list a set of names found and its quantity.

        :param json_project: Dictionary with a JSON data parsed.
        """

        for key, value in json_project.iteritems():
            if key == "targets":
                for dicc in value:
                    for dicc_key, dicc_value in dicc.iteritems():
                        if dicc_key == "costumes":
                            for backdrop in dicc_value:
                                for name_key, name_value in backdrop.iteritems():
                                    if name_key == "name":
                                        for default in self.default_names:
                                            if default in name_value:
                                                self.total_default += 1
                                                self.list_default.append(name_value)


def main(json_project):
    """ The entrypoint for the 'backdropNaming' extension.
    Creates a new instance of the class and assigns to naming their
    attributes and methods. When method finalize is invoked, the object
    return total and list of default backdrop found.

    :param json_project: Dictionary with a JSON data deserialized.
    """
    naming = BackdropNaming()
    naming.analyze(json_project)
    return naming.finalize()
