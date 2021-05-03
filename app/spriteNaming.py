class SpriteNaming:
    """
    Plugin that analyzes a Scratch project to check if the names of the
    sprites are not specific enough, which indicates that the developer has
    not modified the default name that Scratch assigns to an object.

    This class keeps track of how often sprites default names (like
    Sprite1, Sprite2...) are used within a project. Checks if identifying
    names have been assigned to characters or scenarios or if the default
    names have remained. This module retrieves a string with number and
    default sprite names of the selected Scratch project.
    """

    def __init__(self):

        self.total_default = 0
        self.list_default = []
        self.default_names = ["Sprite", "Objeto", "Personatge", "Figura", "o actor", "Personaia"]

    def finalize(self):
        """
        Method of the class which returns the total number of default
        sprite names found in the Scratch project.

        :return result: A string indicate the number and default sprite names.
        """
        result = ""

        result += ("%d default sprite names found:\n" % self.total_default)
        for name in self.list_default:
            result += name
            result += "\n"

        return result

    def analyze(self, json_project):
        """
        Load an sb3 project in JSON format as dictionary object. Parse
        this dictionary to find in key targets values that match the
        names of the default sprites from the given list. Updates class
        attributes when name is found.

        :param json_project: Dictionary whit JSON data of Scratch project
         where sprite names are searched.
        """

        for key, value in json_project.iteritems():
            if key == "targets":
                for dicc in value:
                    for dicc_key, dicc_value in dicc.iteritems():
                        if dicc_key == "name":
                            for default in self.default_names:
                                if default in dicc_value:
                                    self.total_default += 1
                                    self.list_default.append(dicc_value)


def main(json_project):
    """The entrypoint for the 'spriteNaming' extension.

    It calls to methods of the class to check the sprite names of the
    project. To initialize an instance is necessary pass the project
    sb3 in json_project. It creates an object of the class SpriteNaming.
    If the default sprite names match with the list, they are stored
    and counted in class attributes.

    :param json_project: Dictionary with a JSON data deserialized.
    does not have default sprite naming, good job!!!Quit
    """
    naming = SpriteNaming()
    naming.analyze(json_project)
    return naming.finalize()
