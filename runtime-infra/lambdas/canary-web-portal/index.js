const { URL } = require('url');
const synthetics = require('Synthetics');
const log = require('SyntheticsLogger');
const syntheticsConfiguration = synthetics.getConfiguration();
const syntheticsLogHelper = require('SyntheticsLogHelper');

const loadBlueprint = async function () {
    const endpoints = process.env.ENDPOINTS;
    if (!endpoints) {
        throw new Error("ENDPOINTS environment variable is not defined.");
    }

    const urls = endpoints.split(',');
    const takeScreenshot = true;

    syntheticsConfiguration.disableStepScreenshots();
    syntheticsConfiguration.setConfig({
        continueOnStepFailure: true,
        includeRequestHeaders: true,
        includeResponseHeaders: true,
        restrictedHeaders: [],
        restrictedUrlParameters: []
    });

    const page = await synthetics.getPage();

    for (const url of urls) {
        await loadUrl(page, url.trim(), takeScreenshot);
    }
};

const resetPage = async function(page) {
    try {
        await page.goto('about:blank', { waitUntil: ['load', 'networkidle0'], timeout: 30000 });
    } catch (e) {
        synthetics.addExecutionError('Unable to open a blank page. ' + e.message, e);
    }
};

const loadUrl = async function (page, url, takeScreenshot) {
    let stepName = null;
    let domcontentloaded = false;

    try {
        stepName = new URL(url).hostname;
    } catch (e) {
        const errorString = "Error parsing url: " + url + ". " + e.message;
        log.error(errorString);
        throw e;
    }

    await synthetics.executeStep(stepName, async function () {
        const sanitizedUrl = syntheticsLogHelper.getSanitizedUrl(url);
        const response = await page.goto(url, { waitUntil: ['domcontentloaded'], timeout: 30000 });
        if (response) {
            domcontentloaded = true;
            const status = response.status();
            const statusText = response.statusText();
            log.info("Response from url: " + sanitizedUrl + "  Status: " + status + "  Status Text: " + statusText);
            if (status < 200 || status > 299) {
                throw new Error("Failed to load url: " + sanitizedUrl + " " + status + " " + statusText);
            }
        } else {
            const logNoResponseString = "No response returned for url: " + sanitizedUrl;
            log.error(logNoResponseString);
            throw new Error(logNoResponseString);
        }
    });

    if (domcontentloaded && takeScreenshot) {
        await new Promise(r => setTimeout(r, 15000));
        await synthetics.takeScreenshot(stepName, 'loaded');
    }

    await resetPage(page);
};

exports.handler = async () => {
    return await loadBlueprint();
};