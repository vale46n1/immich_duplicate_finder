# Immich Duplicate Finder

## A Comprehensive Solution for Identifying and Managing Duplicate Photos in Immich

![image](https://github.com/vale46n1/immich_duplicate_finder/assets/36825789/933b168d-b7ff-4cd0-8117-92852b6dc1cc)

The "Immich Duplicate Finder" is an tool designed to seamlessly be integrated with the Immich API, targeting the efficient detection and management of duplicate images through hashing detection (and future incorporation of machine learning technologies). Project aims to enhance storage optimization and organization within the Immich ecosystem.

### Features:

- **Highly Accurate Detection:** Utilizes state-of-the-art algorithms to identify duplicates with precision based on hashing values.
- **Easy Integration:** Designed to be effortlessly integrated with existing Immich installations, ensuring a smooth user experience without disrupting the workflow.
- **Performance Optimized:** Engineered for minimal resource consumption, ensuring fast and efficient duplicate detection even in large datasets.
- **User-Friendly Interface:** Comes with a simple and intuitive interface, making it accessible to both technical and non-technical users, further enriched by the comparison slider for an enhanced visual interaction.

### Future development:

- **Auto Deletion Options:** Multiple ways to handle detected duplicates, including auto-deletion, manual review, and archival solutions.

## Getting Started

"Immich Duplicate Finder" is built as a Streamlit app in Python, making it easy to deploy and use with just a few steps. Follow these instructions to get up and running:

### Clone the Repository

Begin by cloning this repository to your local machine. You can do this by running the following command in your terminal or command prompt:

```bash
git clone https://github.com/vale46n1/immich_duplicate_finder.git
```

### Install Dependencies

Navigate to the cloned repository's directory and install the required dependencies using the provided `requirements.txt` file:

```bash
cd immich_duplicate_finder
pip install -r requirements.txt
```
This command installs all necessary Python packages that "Immich Duplicate Finder" relies on.

### Launch the App
With the dependencies installed, you can now launch the Streamlit app. Execute the following command:
```bash
streamlit run app.py
```
This will start the Streamlit server and automatically open your web browser to the app's page. Alternatively, Streamlit will provide a local URL you can visit to view the app.

## Initial Configuration

After launching the app, you'll need to complete a simple initial configuration to connect the "Immich Duplicate Finder" with your Immich server:

1. **Specify Immich Server Address:** Upon first launching the app, in the sidebar, you'll be prompted to enter the address of your Immich server. This ensures that the "Immich Duplicate Finder" can communicate with your Immich installation.

2. **Generate an API Key:** Next, generate an API key within your Immich app. This is a critical step for authenticating and securing communication between the "Immich Duplicate Finder" and the Immich server.
https://immich.app/docs/features/command-line-interface#obtain-the-api-key

4. **Enter the API Key into the Program:** Once you have your API key, enter it into the designated field in the "Immich Duplicate Finder" app. This links your specific Immich instance to the duplicate finder.

5. **Data Persistence:** To streamline your experience, the server address and API key are securely saved in a database. This means you won't need to re-enter this information every time you use the app, making future interactions quicker and more seamless.

## Disclaimer

This software is provided "as is", without any warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

This program is still under development and may contain bugs or defects that could lead to data loss or damage. Users are cautioned to use it at their own risk. The developers assume no responsibility for any damages, loss of information, or any other kind of loss resulting from the use of this program.


Enjoy exploring and managing duplicates in your Immich ecosystem with ease! If you encounter any issues or have suggestions for improvement, feel free to open an issue or submit a pull request.
