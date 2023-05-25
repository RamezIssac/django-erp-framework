(function () {
    var ValueError, create, explicitToImplicit, format, implicitToExplicit, lookup, resolve,
        __hasProp = Object.prototype.hasOwnProperty,
        __extends = function (child, parent) {
            for (var key in parent) {
                if (__hasProp.call(parent, key)) child[key] = parent[key];
            }
            function ctor() {
                this.constructor = child;
            }

            ctor.prototype = parent.prototype;
            child.prototype = new ctor;
            child.__super__ = parent.prototype;
            return child;
        },
        __slice = Array.prototype.slice;

    ValueError = (function (_super) {

        __extends(ValueError, _super);

        function ValueError(message) {
            this.message = message;
        }

        ValueError.prototype.name = 'ValueError';

        return ValueError;

    })(Error);

    implicitToExplicit = 'cannot switch from implicit to explicit numbering';

    explicitToImplicit = 'cannot switch from explicit to implicit numbering';

    create = function (transformers) {
        if (transformers == null) transformers = {};
        return function () {
            var args, explicit, idx, implicit, message, template;
            template = arguments[0], args = 2 <= arguments.length ? __slice.call(arguments, 1) : [];
            idx = 0;
            explicit = implicit = false;
            message = 'cannot switch from {} to {} numbering';
            return template.replace(/([{}])\1|[{](.*?)(?:!(.+?))?[}]/g, function (match, literal, key, transformer) {
                var value, _ref, _ref2;
                if (literal) return literal;
                if (key.length) {
                    if (implicit) throw new ValueError(implicitToExplicit);
                    explicit = true;
                    value = (_ref = lookup(args, key)) != null ? _ref : '';
                } else {
                    if (explicit) throw new ValueError(explicitToImplicit);
                    implicit = true;
                    value = (_ref2 = args[idx++]) != null ? _ref2 : '';
                }
                if (Object.prototype.hasOwnProperty.call(transformers, transformer)) {
                    return transformers[transformer](value);
                } else {
                    return value;
                }
            });
        };
    };

    lookup = function (object, key) {
        var match;
        if (!/^(\d+)([.]|$)/.test(key)) key = '0.' + key;
        while (match = /(.+?)[.](.+)/.exec(key)) {
            object = resolve(object, match[1]);
            key = match[2];
        }
        return resolve(object, key);
    };

    resolve = function (object, key) {
        var value;
        value = object[key];
        if (typeof value === 'function') {
            return value.call(object);
        } else {
            return value;
        }
    };

    format = create({});

    format.create = create;

    format.extend = function (prototype, transformers) {
        var $format;
        $format = create(transformers);
        prototype.format = function () {
            return $format.apply(null, [this].concat(__slice.call(arguments)));
        };
    };

    if (typeof module !== 'undefined') {
        module.exports = format;
    } else if (typeof define === 'function' && define.amd) {
        define(format);
    } else {
        window.format = format;
    }

}).call(this);
