from PyQt5.QtCore import pyqtSlot
from selenium import webdriver
from time import sleep
from threading import Thread
import json

from PyQt5 import QtWidgets, uic
import sys, os
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtCore, QtGui

class Exemplars:

    exemplarPath = ''
    jsonObj = None

    def __init__(self, exemplarPath):
        self.jsonObj = []
        self.exemplarPath = exemplarPath

    def loadingExemplars(self):
        with open(self.exemplarPath, 'r', encoding="utf8") as rf:
            self.jsonObj = json.load(rf)

    def getAllTaskIds(self):
        task_ids = []
        for task_id in self.jsonObj:
            task_ids.append(task_id)
        return task_ids

    def extractTextBetweenTwoString(self, text, sub1, sub2):
        return ''.join(text.split(sub1)[1].split(sub2)[0])

    def getTaskData(self, task_id):
        specifier = self.jsonObj[task_id]['Specifier']
        task = ""
        if (len(specifier) > 0):
            task = self.extractTextBetweenTwoString(specifier[0], "Task:", "State:").strip()

        return task

    def getSubtaskData(self, task_id):
        subtasks = []
        states = []
        observations = []
        demonstrations = self.jsonObj[task_id]['Demonstrations']
        for demonstration in demonstrations:
            for demonstration_obj in demonstration:
                subtasks.append(demonstration_obj['Reformation'])
                states.append(demonstration_obj['State'])
                observations.append(demonstration_obj['Observation'][0])
                break
        return subtasks, states, observations

    def removeTask(self, task_id):
        self.jsonObj.pop(task_id)

    def apply(self, task_result):
        exemplar_name = task_result['id']
        subtaskReformation = "You are a subtasker which divides a task into subtasks according to given examples.\n\nTask:\n" + \
                             task_result['Task'] + "\nSubtasks:\n"
        subtask_ind = 1
        demonstrations = []
        for subtask in task_result['Subtasks']:
            subtaskReformation += str(subtask_ind) + ". `" + subtask['command'] + "` \n"
            subtask_ind = subtask_ind + 1

            plan = ''
            action_ind = 1
            for action in subtask['actions']:
                if action['type'] == 'click':
                    plan += str(action_ind) + ". `" + action['type'] + " " + action['element'] + "`\n"
                elif action['type'] == 'type':
                    plan += str(action_ind) + ". `" + action['type'] + " '" + action['content'] + "'`\n"
                else:
                    plan += str(action_ind) + ". `" + action['type'] + "'`\n"
                action_ind = action_ind + 1

            dictObj = {
                "State": subtask['state'],
                "Observation": [subtask['observation']],
                "Reformation": subtask['command'],
                "Plan": plan
            }

            demonstrations.append(dictObj)

        prompts = []
        exist = 0
        if exemplar_name in self.jsonObj:
            exist = 1
            prompts = self.jsonObj[exemplar_name]

        if exist == 1:
            self.jsonObj[exemplar_name]['SubtaskReformation'] = self.jsonObj[exemplar_name]['SubtaskReformation'] + "\n\n" + subtaskReformation
            demonstration_ind = 0
            for demonstration in demonstrations:
                self.jsonObj[exemplar_name]['Demonstrations'][demonstration_ind].append(demonstration)
                demonstration_ind = demonstration_ind + 1
        else:
            demonstrations_new = []
            for demonstration in demonstrations:
                demonstrations_new.append([demonstration])
            self.jsonObj[exemplar_name] = {
                "Description": "\"type\": Type a string via the keyboard, \"press\": Press a key on the keyboard, including \"enter\", \"space\", \"tab\", \"click\": Press click.\n",
                "Specifier": ["Task: " + task_result['Task'] + "\nState:\n" + task_result['initial_state']],
                "ObsFilterPrefix": [
                    [
                        "You are a web scraping agent which extracts the html elements according to examples"
                    ],
                    [
                        "You are a web scraping agent which filters the list of html elements to pick departure flights according to examples."
                    ],
                    [
                        "You are a web scraping agent which filters the list of html elements to pick departure flights according to examples."
                    ]
                ],
                "SubtaskReformation": subtaskReformation,
                "Demonstrations": demonstrations_new,
            }

    def export(self, filepath):
        #with open(self.exemplarPath + "_1.json", "w") as outfile:
        with open(filepath, "w", encoding="utf8") as outfile:
            json.dump(self.jsonObj, outfile, ensure_ascii=False, indent=4)

class Ui(QtWidgets.QDialog):

    folderPath = ''
    jsonObj = None
    exemplarObj = None
    webBrowser = None
    task_result = None
    state = ''
    subtask_selected = -1

    def __init__(self):
        super(Ui, self).__init__()

        # Load the UI Page - added path too
        self.folderPath = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi("window.ui", self)

        # Initialize
        self.but_testjs.clicked.connect(self.but_testjs_clicked)
        self.but_open.clicked.connect(self.but_open_clicked)
        self.but_export.clicked.connect(self.but_export_clicked)
        self.but_remove.clicked.connect(self.but_remove_clicked)
        self.but_delete.clicked.connect(self.but_delete_clicked)
        self.but_finalize.clicked.connect(self.but_finalize_clicked)
        self.but_connect.clicked.connect(self.but_connect_clicked)
        self.but_getstate.clicked.connect(self.but_getstate_clicked)
        self.but_append.clicked.connect(self.but_append_clicked)
        self.but_clear.clicked.connect(self.but_clear_clicked)
        self.input_url.setText('https://www.google.com/travel/flights')
        self.list_task.itemDoubleClicked.connect(self.list_task_selected)
        self.list_task.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_task_content.itemDoubleClicked.connect(self.list_task_content_selected)
        self.show()
        self.task_result = []

        self.thread = Thread(target=self.get_response)
        self.thread.start()

    def get_response(self):
        while True:
            sleep(3)
            if self.webBrowser != None:
                self.list_actions.clear()
                response = self.webBrowser.getResponse()
                if (response != ""):
                    list = []
                    for item in response:
                        list_item = "[" + item['tagName'] + "] " + item['action']
                        list.append(list_item)

                    self.list_actions.addItems(list)

    def but_testjs_clicked(self):
        if self.webBrowser != None:
            self.webBrowser.testJS()
            QMessageBox.information(self, 'Notification', 'Successful!')

    def but_export_clicked(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        fileName, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Exemplar", "", "JSON Files(*.json);;All Files(*)", options=options)
        if fileName.endswith(".json") == False:
            fileName = fileName + ".json"
        if fileName:
            self.exemplarObj.export(fileName)
            QMessageBox.information(self, 'Notification', 'Successfully Saved.')

    def but_open_clicked(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Exemplar", "", "JSON Files(*.json);;All Files(*)", options=options)
        if fileName:
            self.input_file.setText(fileName)
            #exemplarPath = os.path.join(self.folderPath, "exemplars.json")
            self.exemplarObj = Exemplars(fileName)
            self.exemplarObj.loadingExemplars()
            self.refresh_listtask()

    def but_connect_clicked(self):
        chromedriverpath = os.path.join(self.folderPath, "chromedriver.exe")
        self.webBrowser = WebBrowserPlay(self.input_url.text(), chromedriverpath)
        self.webBrowser.runn()

    def but_remove_clicked(self):
        task_ids = self.exemplarObj.getAllTaskIds()
        items = self.list_task.selectedItems()
        if len(items) == 0:
            return
        userResponse = QMessageBox.question(self, 'Question', "Will you remove these tasks?",
                                            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if userResponse == QMessageBox.Yes:
            x = []
            for i in range(len(items)):
                txt = str(self.list_task.selectedItems()[i].text())
                x.append(txt)
            for txt in x:
                if txt in task_ids:
                    if self.exemplarObj != None:
                        self.exemplarObj.removeTask(txt)
                        self.refresh_listtask()

    def refresh_listtask(self):
        if self.exemplarObj != None:
            self.list_task.clear()
            task_ids = self.exemplarObj.getAllTaskIds()
            self.list_task.addItems(task_ids)

    def but_delete_clicked(self):
        items = self.list_task_content.selectedItems()
        if len(items) == 0:
            return
        for item in items:
            if item.text()[1:3] == ". ":
                subtask_title = item.text()[3:]
                ind = 0
                for subtask in self.task_result:
                    if subtask['title'] == subtask_title:
                        userResponse = QMessageBox.question(self, 'Question', "Will you remove this subtask '" + subtask_title + "'?",
                                                            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

                        if userResponse == QMessageBox.Yes:
                            self.task_result.pop(ind)
                            self.input_subtask.setText("")
                            self.input_state.setPlainText("")
                            self.input_observation.setPlainText("")
                        break
                    ind = ind + 1
                self.renderTaskResult()

    def but_clear_clicked(self):
        # self.input_subtask.setText("")
        self.state = ''
        if self.webBrowser != None:
            self.webBrowser.clearCache()

    def list_task_selected(self, item):
        self.input_task_id.setText(item.text())
        task = self.exemplarObj.getTaskData(item.text())
        self.input_task.setText(task)
        subtasks, states, observations = self.exemplarObj.getSubtaskData(item.text())
        self.task_result = []
        ind = 0
        for subtask in subtasks:
            obj = {}
            obj['title'] = subtask
            obj['state'] = states[ind]
            obj['observation'] = observations[ind]
            obj['response'] = ''
            self.task_result.append(obj)
            ind = ind + 1

        self.renderTaskResult()

    def list_task_content_selected(self, item):
        if item.text()[1:3] == ". ":
            subtask_title = item.text()[3:]
            ind = 0
            for subtask in self.task_result:
                if subtask['title'] == subtask_title:
                    self.input_subtask.setText(subtask['title'])
                    self.input_observation.setPlainText(subtask['observation'])
                    self.input_state.setPlainText(subtask['state'])
                    # self.list_actions.clear()
                    # list = []
                    # for item in subtask['response']:
                    #     list_item = "[" + item['tagName'] + "] " + item['action']
                    #     list.append(list_item)
                    #
                    # self.list_actions.addItems(list)
                    break
                ind = ind + 1
            self.subtask_selected = ind

    def but_finalize_clicked(self):
        task_result_string = {}
        task_result_string['Task'] = self.input_task.toPlainText()
        task_result_string['id'] = self.input_task_id.text()
        task_result_string['initial_state'] = ''
        task_result_string['Subtasks'] = []
        kk = 0
        for subtask in self.task_result:
            subtask_string = {}
            subtask_string['command'] = subtask['title']
            subtask_string['state'] = subtask['state']
            if kk == 0:
                task_result_string['initial_state'] = subtask['state']
            subtask_string['observation'] = subtask['observation']
            subtask_string['actions'] = []
            for response in subtask['response']:
                action_string = {}
                action_string['type'] = response['action']
                if (response['action'] == 'click'):
                    action_string['element'] = response['elem']
                else:
                    action_string['element'] = ''
                action_string['content'] = response['content']
                subtask_string['actions'].append(action_string)
            task_result_string['Subtasks'].append(subtask_string)
            kk = kk + 1

        if kk > 0:
            self.exemplarObj.apply(task_result_string)

        self.task_result = []
        # self.thread.stop()
        self.webBrowser.close()
        self.webBrowser = None
        # self.thread.join()

        self.refresh_listtask()
        self.input_task_id.setText("")
        self.input_task.setText("")
        self.list_task_content.clear()

    def but_getstate_clicked(self):
        states = self.webBrowser.getInitialState()
        self.input_state.setPlainText("\n".join(states))

    def but_append_clicked(self):
        if self.input_subtask.toPlainText() == "":
            return

        if self.webBrowser == None:
            return

        userResponse = QMessageBox.question(self, 'Question', "Will you add a subtask newly or update?",
                                            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)

        if userResponse == QMessageBox.Yes:
            subtask = {}
            subtask['title'] = self.input_subtask.toPlainText()
            subtask['state'] = self.input_state.toPlainText()
            subtask['observation'] = self.input_observation.toPlainText()
            subtask['response'] = self.webBrowser.getResponse()
            self.task_result.append(subtask)
        elif userResponse == QMessageBox.No:
            self.task_result[self.subtask_selected]['title'] = self.input_subtask.toPlainText()
            self.task_result[self.subtask_selected]['state'] = self.input_state.toPlainText()
            self.task_result[self.subtask_selected]['observation'] = self.input_observation.toPlainText()
            if self.task_result[self.subtask_selected]['response'] == "":
                self.task_result[self.subtask_selected]['response']= self.webBrowser.getResponse()
            self.subtask_selected = -1

        self.input_subtask.setText("")
        self.input_state.setPlainText("")
        self.input_observation.setPlainText("")
        self.state = ''
        self.webBrowser.clearCache()
        self.renderTaskResult()

    def renderTaskResult(self):
        self.list_task_content.clear()
        items = []
        ind = 1
        for subtask in self.task_result:
            item = str(ind) + '. ' + subtask['title']
            ind = ind + 1
            items.append(item)
            for itemm in subtask['response']:
                text = "[" + itemm['tagName'] + "] " + itemm['action']
                items.append(text)

        self.list_task_content.addItems(items)

class WebBrowserPlay:

    url = ''
    chromedriverpath = ''
    threadStopFlag = 0
    gobuttonclick = 0
    driveropened = 0

    def __init__(self, url, chromedriverpath):
        self.driver = None
        self.url = url
        self.chromedriverpath = chromedriverpath
        self.thread = Thread(target=self.worker)
        self.thread.start()
        self.threadStopFlag = 0
        self.gobuttonclick = 0
        self.driveropened = 0

    def getInitialState(self):
        return self.getElements()

    def close(self):
        # self.threadStopFlag = 1;
        # self.thread.join()
        self.driver.quit()
        self.driver = None

    def appendJS(self):
        js_script = """
            value = [];
            jsChecked = 0;
            if (window.location.hostname == 'www.booking.com')
            {
                var buttons = document.getElementsByTagName('button');
                for (var kk = 0; kk < buttons.length; kk++)
                {
                    if (buttons[kk].innerText == 'Search')
                        buttons[kk].setAttribute('style', 'pointer-events: none');
                }
            }

            window.compare = function(obj1, obj2)
            {
                var ret = 1;
                var keys1 = Object.keys(obj1['attributes']);
                var keys2 = Object.keys(obj2['attributes']);
                if (JSON.stringify(keys1) === JSON.stringify(keys2))
                {
                    for (var kk = 0; kk < keys1.length; kk++)
                    {
                        var key = keys1[kk];
                        if (key != 'class')
                        {
                            if (obj1['attributes'][key] != obj2['attributes'][key])
                                ret = 0;
                        }
                        else
                        {
                            if (obj1['attributes'][key] == obj2['attributes'][key] || obj1['attributes'][key].includes(obj2['attributes'][key]) || obj2['attributes'][key].includes(obj1['attributes'][key]))
                            {
                            }
                            else
                                ret = 0;
                        }
                    }
                }
                else
                    ret = 0;

                return ret;
            }
            window.processElement = function(node)
            {
                var ret = '';
                var nodes = document.getElementsByTagName(node.tagName);
                for (var k = 0; k < nodes.length; k++)
                {
                    var flg = 0;
                    if (node.tagName.toLowerCase() == 'input')
                    {
                        if (compare(nodes[k], node) == 1)
                            flg = 1;
                    }
                    else
                    {
                        if (node.innerText == nodes[k].innerText)
                            flg = 1;
                    }

                    if (flg == 1)
                    {
                        if (node.tagName.toLowerCase() == 'input')
                            ret = '<input type="text">' + node.placeholder + '</input>-- input element index = ' + k;
                        else if (node.tagName.toLowerCase() == 'li')
                            ret = '<li>' + node.innerText + '</li>-- input element index = ' + k;
                        else if (node.tagName.toLowerCase() == 'button')
                            ret = '<button>' + node.innerText + '</button>-- input element index = ' + k;
                        break;
                    }
                }
                return ret;
            }
            window.addClickObj = function(node)
            {
                var obj = {};
                obj['action'] = 'click';
                obj['elem'] = processElement(node);
                obj['content'] = '';
                obj['tagName'] = node.tagName;
                obj['attributes'] = {};
                for (var kk = 0; kk < node.attributes.length; kk++)
                    obj['attributes'][node.attributes[kk].nodeName] = node.attributes[kk].nodeValue;

                value.push(obj);
            }
            
            document.addEventListener("click", clickHandler, true);
            
            function clickHandler(e) 
            {
                console.log(e);
                var node = e.target;
                var found = 0;
                while (true)
                {
                    if (node.tagName.toLowerCase() == "input" || node.tagName.toLowerCase() == "li" || node.tagName.toLowerCase() == "button")
                    {
                        found = 1;
                        break;
                    }
                    else
                        node = node.parentNode;

                    if (node.tagName == "HTML")
                        break;
                }
                if (found == 0 && window.location.hostname == 'www.booking.com')
                {
                    node = e.target;
                    nodes = node.querySelectorAll('button');
                    for (var kk = 0 ; kk < nodes.length; kk++)
                    {
                        if (nodes[kk].getAttribute('data-ui-name') == 'button_search_submit')
                        {
                            node = nodes[kk];
                            found = 1;
                            break;
                        }
                    }
                }
    
                if (found == 1)
                    addClickObj(node);
                    
                if (window.location.hostname == 'www.booking.com')
                {
                    if (node.innerText == 'Search' && node.tagName.toLowerCase() == 'button')
                    {
                        setInterval(function () {
                            if (value.length == 0)
                                node.click();
                            console.log('cc');
                        }, 1000);
                    } 
                }
            }

            document.addEventListener("keyup", keyHandler, true);

            function keyHandler(event)
            {
                if (event.keyCode == 13) // New Line
                {
                    var obj = {};
                    obj['action'] = 'press enter';
                    obj['elem'] = processElement(event.target);
                    obj['content'] = '';
                    obj['tagName'] = event.target.tagName;
                    obj['attributes'] = {};
                    for (var kk = 0; kk < event.target.attributes.length; kk++)
                        obj['attributes'][event.target.attributes[kk].nodeName] = event.target.attributes[kk].nodeValue;
                    value.push(obj);
                }
                else if (event.keyCode == 9) // Tab
                {
                    var obj = {};
                    obj['action'] = 'press tab';
                    obj['elem'] = processElement(event.target);
                    obj['content'] = '';
                    obj['tagName'] = event.target.tagName;
                    obj['attributes'] = {};
                    for (var kk = 0; kk < event.target.attributes.length; kk++)
                        obj['attributes'][event.target.attributes[kk].nodeName] = event.target.attributes[kk].nodeValue;
                    value.push(obj);
                }
                else
                {
                    var obj = {};
                    obj['action'] = 'type';
                    obj['elem'] = processElement(event.target);
                    obj['content'] = event.target.value;
                    obj['tagName'] = event.target.tagName;
                    obj['attributes'] = {};
                    for (var kk = 0; kk < event.target.attributes.length; kk++)
                        obj['attributes'][event.target.attributes[kk].nodeName] = event.target.attributes[kk].nodeValue;

                    var flg = 0;
                    if (value.length > 0)
                    {
                        if (value[value.length - 1]['action'] == 'type')
                        {
                            flg = 1;
                            value[value.length - 1]['content'] = obj['content'];
                        }
                    }
                    if (flg == 0)
                        value.push(obj);
                }
            }
            
            window.jsCheck = function()
            {
                jsChecked = 1;
                return jsChecked;
            }
        """

        self.driver.execute_script(js_script)

    def worker(self):
        while True:
            if self.gobuttonclick == 1:
                if self.driveropened == 0:
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service)
                    # self.driver = webdriver.Chrome(executable_path=self.chromedriverpath)
                    self.driver.get(self.url)

                    self.appendJS()
                    self.driveropened = 1

            if self.threadStopFlag == 0:
                sleep(1)
            else:
                break
        #     response = self.driver.execute_script(r_script)
        #     print(response)

    def runn(self):
        self.driveropened = 0
        self.gobuttonclick = 1

    def getResponse(self):
        response = ''
        if self.driver != None:
            script = 'if (typeof value !== "undefined") return value; else return "";'
            try:
                response = self.driver.execute_script(script)
            except:
                response = ''
        return response

    def testJS(self):
        if self.driver != None:
            script = 'if (typeof value !== "undefined") return 1; else return 0;'
            try:
                response = self.driver.execute_script(script)
            except:
                response = ''
            if (response == 1):
                print('Success')
            else:
                self.appendJS()


    def clearCache(self):
        if self.driver != None:
            script = 'value = [];'
            try:
                response = self.driver.execute_script(script)
            except:
                response = ''

    def extract_placeholder(self, html, placeholder):
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')

        # Find the input element and extract the placeholder attribute's value
        input_element = soup.find('input', {'type': 'text'})
        placeholder_value = input_element[f'{placeholder}']
        return placeholder_value

    def getElements(self):
        input_elements = self.driver.find_elements(By.TAG_NAME, "input")
        span_elements = self.driver.find_elements(By.TAG_NAME, "span")
        button_elements = self.driver.find_elements(By.TAG_NAME, "button")
        li_elements = [x for x in self.driver.find_elements(By.TAG_NAME, "li") if len(x.text)][:5]

        important_elements = []
        selenium_elements = []
        i = 0
        # Extract and print the placeholders
        for element in input_elements:
            try:
                # element.click()
                input_element = element.get_attribute('outerHTML') + f'-- input element index = {i}'
                # print(element.get_attribute('outerHTML') + f'-- input element index = {i}')
                try:
                    input_element = self.extract_placeholder(input_element, 'placeholder')
                except:
                    input_element = self.extract_placeholder(input_element, 'value')

                important_elements.append(
                    '''<input type="text"''' + input_element + '</input>' + f'-- input element index = {i}')
                selenium_elements.append(element)
                i = i + 1
            except:
                pass

        for element in li_elements:
            try:
                li_element = element.text
                try:
                    li_element = li_element.strip().replace("\n", " ")
                    # print('button is', button_element)
                    li_element = '<li> ' + li_element + '</li' + f'-- input element index = {i}'
                    important_elements.append(li_element)
                except:
                    important_elements.append(li_element)
                selenium_elements.append(element)
                i = i + 1
            except:
                pass

        for element in button_elements:
            try:
                button_element = element.text
                try:
                    button_element = button_element.strip().replace("\n", " ")
                    # print('button is', button_element)
                    if button_element != '':
                        button_element = '<button> ' + button_element + '</button' + f'-- input element index = {i}'
                        important_elements.append(button_element)
                except:
                    important_elements.append(button_element)
                selenium_elements.append(element)
                i = i + 1
            except:
                pass

        return important_elements


if __name__ == '__main__':
    # webBrowser = WebBrowserPlay()
    # webBrowser.run()
    app = QtWidgets.QApplication(sys.argv)
    main = Ui()
    app.exec_()
