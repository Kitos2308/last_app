import itertools
import operator


class Serializer(object):
    def __init__(self, input_data, model):
        self._data = input_data
        self.model_type = type(model)
        self.model = model if self.model_type == dict else model[0]

        self.nested = list(self.__nested())
        self.nested_keys = None
        self.shifted = list(self.__shifted(self.model.items()))
        self.shifted_child = list(self.__get_shifted_child(self.shifted, self.model))
        self.this_keys = self.__get_this_level_keys()
        self.serialized_data = None

    def __get_shifted_child(self, shifted, model):
        for group in shifted:
            f = list(self.__shifted(model[group].items()))
            for key in model[group].keys():
                if key not in f:
                    yield key
            if f:
                for x in self.__get_shifted_child(f, model[group]):
                    yield x

    def __get_this_level_keys(self):
        return list(set(self.model.keys()) - set(self.shifted) - set(self.nested))

    def __nested(self):
        for key, value in self.model.items():
            if self.__is_nested(value):
                yield key

    def __is_nested(self, item):
        if isinstance(item, list):
            return True
        if isinstance(item, dict):
            for key, value in item.items():
                if self.__is_nested(value):
                    return True
        return False

    def __shifted(self, items):
        for key, value in items:
            if not self.__is_nested(value) and isinstance(value, dict):
                yield key

    @staticmethod
    def __embed(data, keys, group_name):
        if data.get(group_name) is None:
            data[group_name] = {}
        for key in keys:
            data[group_name].update({key: data.pop(key)})
        return data

    def shift(self, data, group_name, model):
        if data.get(group_name) is None:
            data[group_name] = {}
        f = list(self.__shifted(model[group_name].items()))
        if f:
            for key in f:
                self.shift(data, key, model[group_name])

        for key in model[group_name].keys():
            data[group_name].update({key: data.pop(key)})

    def serialize(self) -> list or dict:
        if len(self._data) <= 0:
            return list()
        result = self._data.copy()
        for row in result:
            for key in self.nested:
                row = self.__embed(row, list(self.__get_keys(self.model[key])), key)

        result = self.__group_data(result, [*self.shifted_child, *self.this_keys])

        for row in result:
            for group in self.nested:
                row[group] = Serializer(row[group], self.model[group]).serialize()

        for group in self.shifted:
            for row in result:
                self.shift(row, group, self.model)
        if self.model_type == dict:
            result = result[0]
        return result

    @staticmethod
    def __group_data(data: list, group_keys):
        if isinstance(data, dict):
            return data
        result = []

        by_value = operator.itemgetter(*group_keys)

        def null_sort_key_getter(row):
            if len(row) > 1:
                a = by_value(row)
                b = map(str, a)
                c = tuple(b)
                return tuple(map(str, by_value(row)))
            else:
                return str(by_value(row))

        for key, group in itertools.groupby(sorted(data, key=null_sort_key_getter), by_value):
            if len(group_keys) > 1:
                result_item = dict(zip(group_keys, key))
            else:
                result_item = {group_keys[0]: key}
            for thing in group:
                for k in group_keys:
                    thing.pop(k, None)
                for x in thing:
                    if result_item.get(x) is None:
                        result_item[x] = [thing[x]]
                    else:
                        result_item[x].append(thing[x])
            result.append(result_item)

        return result

    def __get_keys(self, data):
        if isinstance(data, dict):
            for x in data:
                if isinstance(data[x], (dict, list)):
                    for y in self.__get_keys(data[x]):
                        yield y
                else:
                    yield x
        if isinstance(data, list):
            for y in self.__get_keys(data[0]):
                yield y

    @staticmethod
    def __glue(data: list):
        out = []
        for v in data:
            if v not in out:
                out.append(v)
        return out
