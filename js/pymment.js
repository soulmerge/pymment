(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define(['Promise'], factory);
    } else {
        // Browser globals (root is window)
        root.pymments = factory(Promise);
    }
}(this, function(Promise) {

    var User = function(pymments, id, name, password) {
        this.pymments = pymments;
        this.id = id;
        this.name = name;
        this.password = password;
    };

    User.current = function(pymments) {
        var userJson = localStorage.getItem('pymments-user');
        if (!userJson) {
            return null;
        }
        userJson = JSON.parse(userJson);
        var id = userJson.id;
        if (id in pymments.userInstances) {
            return pymments.userInstances[id];
        }
        var user = User.fromJson(pymments, userJson);
        pymments.userInstances[id] = user;
        return user;
    };

    User.fromJson = function(pymments, json) {
        return new User(
            pymments,
            json.id,
            json.name,
            json.password
        );
    };

    User.create = function(pymments, name) {
        return pymments.request("POST", {
            op: "user",
            name: name
        }).then(function(json) {
            localStorage.setItem('pymments-user', JSON.stringify(json));
            return pymments.user(json.id, json);
        });
    };

    User.prototype.changeName = function(newName) {
        var self = this;
        return self.pymments.request("POST", {
            op: "username",
            name: newName,
            id: self.id,
            password: self.password
        }).then(function(json) {
            self.name = newName;
            localStorage.setItem('pymments-user', JSON.stringify(json));
        });
    };

    var Comment = function(id, parent, user, message, time) {
        this.id = id;
        this.parent = parent;
        this.user = user;
        this.message = message;
        this.time = time;
    };

    Comment.fromJson = function(pymments, json) {
        var user = pymments.user(json.user.id, json.user);
        var parent = null;
        if (json.parent) {
            parent = pymments.comment(json.parent.id, json.parent);
        }
        return new Comment(
            json.id,
            parent,
            user,
            json.message,
            new Date(json.time * 1000)
        );
    };

    var Item = function(pymments, id) {
        this.pymments = pymments;
        this.id = id;
    };

    Item.prototype.comments = function() {
        return new CommentList(this.pymments, this.id);
    }

    Item.prototype.comments_count = function() {
        return this.comments().count();
    }

    Item.prototype.addComment = function(parent, user, message) {
        return this.pymments.request("POST", {
            op: "comment",
            itemId: this.id,
            parentId: parent ? parent.id : null,
            userId: user.id,
            userPassword: user.password,
            message: message
        }).then(function(json) {
            return this.pymments.comment(json.id, json);
        });
    };

    var CommentList = function(pymments, itemId) {
        this.pymments = pymments;
        this.itemId = itemId;
        this.lastId = 0;
        this.promise = null;
        this.finished = false;
    };

    CommentList.prototype.nextPage = function() {
        if (this.finished) {
            return Promise.reject('done');
        }
        var self = this;
        if (self.promise) {
            var promise = self.promise.then(function() {
                return self.nextPage().then(function(result) {
                    if (self.promise === promise) {
                        self.promise = null;
                    }
                    return result;
                });
            });
            self.promise = promise;
            return promise;
        }
        var promise = self.pymments.request("GET", {
            op: "comments",
            itemId: self.itemId,
            lastId: self.lastId
        }).then(function(result) {
            var comments = [];
            for (var i = 0; i < result.length; i++) {
                var json = result[i];
                comments.push(self.pymments.comment(json.id, json));
            }
            if (comments.length != 10) {
                self.finished = true;
            }
            self.lastId = comments[comments.length - 1].id;
            if (self.promise === promise) {
                self.promise = null;
            }
            return comments;
        });
        self.promise = promise;
        return self.promise;
    };

    CommentList.prototype.count = function() {
        if (!this.countPromise) {
            this.countPromise = pymments.request("GET", {
                op: "count",
                itemId: this.itemId
            });
        }
        return this.countPromise;
    };

    var pymments = function(url) {
        this.remoteUrl = url;
        this.itemInstances = {};
        this.commentInstances = {};
        this.userInstances = {};
    };

    pymments.prototype.item = function(id) {
        if (!('' + id).match(/^\d+$/)) {
            throw new Error('Id must be numeric');
        }
        if (!(id in this.itemInstances)) {
            this.itemInstances[id] = new Item(this, id);
        }
        return Promise.resolve(this.itemInstances[id]);
    };

    pymments.prototype.comment = function(id, json) {
        var self = this;
        if (id in self.commentInstances) {
            if (json) {
                return self.commentInstances[id];
            }
            return Promise.resolve(self.commentInstances[id]);
        }
        if (json) {
            var comment = Comment.fromJson(self, json);
            self.commentInstances[id] = comment;
            return comment;
        }
        return self.request("GET", {
            op: "comment",
            id: id
        }).then(function(json) {
            return Comment.fromJson(self, json);
        }).then(function(comment) {
            self.commentInstances[id] = comment;
            return comment;
        });
        return Promise.resolve(this.commentInstances[id]);
    };

    pymments.prototype.localUser = function() {
        return User.current(this);
    };

    pymments.prototype.createUser = function(name) {
        return User.create(this, name);
    };

    pymments.prototype.user = function(id, json) {
        var self = this;
        if (id in self.userInstances) {
            if (json) {
                return self.userInstances[id];
            }
            return Promise.resolve(self.userInstances[id]);
        }
        if (json) {
            var user = User.fromJson(self, json);
            self.userInstances[id] = user;
            return user;
        }
        return self.request("GET", {
            op: "user",
            id: id
        }).then(function(json) {
            return User.fromJson(self, json);
        }).then(function(user) {
            self.userInstances[id] = user;
            return user;
        });
        return Promise.resolve(this.userInstances[key]);
    };

    pymments.prototype.request = function(method, parameters) {
        var self = this;
        paramList = [];
        for (var param in parameters) {
            paramList.push(encodeURI(param) + '=' + encodeURI(parameters[param]));
        }
        parameters = paramList.join('&');
        return new Promise(function(resolve, reject) {
            var request = new XMLHttpRequest();
            request.onreadystatechange = function() {
                if (request.readyState != 4) {
                    return;
                }
                if (request.status == 200) {
                    resolve(JSON.parse(request.responseText));
                } else if (typeof onerror === "function") {
                    reject(request);
                }
            }
            var url = self.remoteUrl;
            if (method === "GET") {
                url += '?' + parameters
            }
            request.open(method, url);
            if (method === "GET") {
                request.send();
            } else {
                request.send(parameters);
            }
        });
    };
    
    pymments.prototype.comments = function(itemId) {
        return this.item(itemId).then(function(item) {
            return item.comments();
        });
    };

    pymments.prototype.comments_count = function(itemId) {
        return this.item(itemId).then(function(item) {
            return item.comments_count();
        });
    };

    pymments.prototype.addComment = function(itemId, parent, user, message) {
        return this.item(itemId).then(function(item) {
            return item.addComment(parent, user, message);
        });
    };

    return pymments;

}));
