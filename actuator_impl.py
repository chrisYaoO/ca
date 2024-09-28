import importlib


class ActuatorImpl:

    @classmethod
    def load_algorithm(cls, algorithm_file: str):
        try:
            module = importlib.import_module(algorithm_file)
            return module
        except ImportError as e:
            print(e)
            return None

    @classmethod
    def run_actuator(cls, algorithm_file: str):
        module = cls.load_algorithm(algorithm_file)
        if module:
            class_name = module.__all__[0]
            algo_class = getattr(module, class_name)
            algo = algo_class()
            return algo.run()
        else:
            return None


if __name__ == '__main__':
    accuracy=ActuatorImpl.run_actuator('cnn_inference')
