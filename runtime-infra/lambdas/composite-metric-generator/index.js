const handler = async (event) => {
    console.info("New event received ", event);
    return {
        success: true
    }
};

module.exports = {
    handler
}