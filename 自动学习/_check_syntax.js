var fs = require('fs');
var path = require('path');
var code = fs.readFileSync(path.join(__dirname, 'auto_learn_pip_loop.js'), 'utf8');

try {
    var vm = require('vm');
    new vm.Script(code);
    console.log('语法检查通过');
} catch(e) {
    console.error('语法错误:', e.message);
}
