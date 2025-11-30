import { useState, useRef } from 'react'
import Sidebar from './components/Sidebar'
import InvoicesView from './components/InvoicesView'
import InventoryView from './components/InventoryView'
import ProductForm from './components/ProductForm'

function App() {
  const [isScanModalOpen, setIsScanModalOpen] = useState(false)
  const [isProductFormOpen, setIsProductFormOpen] = useState(false)
  const [productFormInitialData, setProductFormInitialData] = useState<any>(null)
  const [activeTab, setActiveTab] = useState('home')
  const [extractedData, setExtractedData] = useState<any[]>([])
  const [isMergeMode, setIsMergeMode] = useState(false)
  const [mergeSummary, setMergeSummary] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleScanClick = () => {
    setIsScanModalOpen(true)
  }

  const handleNavigate = (tab: string) => {
    setActiveTab(tab)
  }

  const handleCameraClick = () => {
    alert("Camera mode is not yet implemented. This would open the device camera.")
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setIsLoading(true)
      setIsScanModalOpen(false)
      setActiveTab('ingestion')
      setIsMergeMode(false) // Reset merge mode
      setMergeSummary(null)

      const formData = new FormData()
      formData.append('file', file)

      try {
        const response = await fetch('http://localhost:8000/api/upload', {
          method: 'POST',
          body: formData,
        })

        if (response.status === 409) {
          const result = await response.json();
          // Show data for review before merging
          setExtractedData(result.data);
          setIsMergeMode(true);
          setMergeSummary(result.summary);
          alert(`Duplicate Invoice Detected!\nSupplier: ${result.summary.supplier_name}\nInvoice No: ${result.summary.invoice_number}\n\nPlease review the items below. Click "Merge to Inventory" to update stock.`);
          setIsLoading(false);
          return;
        }

        if (!response.ok) {
          throw new Error(`Upload failed: ${response.statusText}`)
        }

        const result = await response.json()
        setExtractedData(result.data)
      } catch (error) {
        console.error("Error uploading file:", error)
        alert("Failed to analyze invoice. Please try again.")
      } finally {
        setIsLoading(false)
      }
    }
  }

  return (
    <div className="h-screen bg-[#0f0f0f] text-white font-sans overflow-hidden flex">
      {/* Sidebar */}
      <Sidebar
        onScanClick={handleScanClick}
        activeTab={activeTab}
        onNavigate={handleNavigate}
      />

      {/* Main Content Area */}
      <main className="flex-1 pl-64 p-8 h-full overflow-hidden flex flex-col">
        {activeTab === 'home' && (
          <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
            <h1 className="text-3xl font-bold mb-4">Dashboard</h1>
            <p className="text-gray-400">Welcome to PharmaGPT Glass.</p>
          </div>
        )}

        {activeTab === 'inventory' && (
          <InventoryView />
        )}

        {activeTab === 'catalog' && (
          <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-3xl font-bold">Product Catalog</h1>
                <p className="text-gray-400">Manage your master list of medicines.</p>
              </div>
              <button
                onClick={() => setIsProductFormOpen(true)}
                className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                <span>+ Add Product</span>
              </button>
            </div>

            {/* Placeholder for Catalog List */}
            <div className="bg-[#1a1a1a] rounded-xl border border-white/10 p-8 text-center">
              <p className="text-gray-400 mb-4">Your product catalog will appear here.</p>
              <button
                onClick={() => setIsProductFormOpen(true)}
                className="text-blue-400 hover:text-blue-300 text-sm font-medium"
              >
                Create your first product definition
              </button>
            </div>
          </div>
        )}

        {activeTab === 'invoices' && (
          <InvoicesView />
        )}

        {activeTab === 'ingestion' && (
          <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
            <h1 className="text-3xl font-bold mb-4">Bill Ingestion</h1>
            {isLoading ? (
              <div className="flex items-center gap-3 text-blue-400">
                <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full"></div>
                Processing Invoice...
              </div>
            ) : (
              <div>
                {extractedData.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-white/10 text-gray-400 text-sm">
                          <th className="p-3">Product</th>
                          <th className="p-3">Pack Size</th>
                          <th className="p-3">Batch</th>
                          <th className="p-3">Expiry</th>
                          <th className="p-3">Qty</th>
                          <th className="p-3">Rate</th>
                          <th className="p-3">MRP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extractedData.map((item, idx) => (
                          <tr key={idx} className={`border-b border-white/5 hover:bg-white/5 ${item.is_new_product ? 'bg-blue-500/10' : ''}`}>
                            <td className="p-3">
                              {item.is_new_product ? (
                                <div className="flex items-center gap-2">
                                  <input
                                    type="text"
                                    value={item.product_name}
                                    onChange={(e) => {
                                      const newData = [...extractedData];
                                      newData[idx].product_name = e.target.value;
                                      setExtractedData(newData);
                                    }}
                                    className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-full"
                                  />
                                  <button
                                    onClick={() => {
                                      setProductFormInitialData({
                                        name: item.product_name,
                                        mrp: item.mrp,
                                        manufacturer: item.manufacturer || '',
                                        conversion: 10,
                                        skuUnit: 'Strip',
                                        atomicUnit: 'Tablet',
                                        category: 'Tablet'
                                      });
                                      setIsProductFormOpen(true);
                                    }}
                                    className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded transition-colors"
                                  >
                                    Define
                                  </button>
                                </div>
                              ) : (
                                <input
                                  type="text"
                                  value={item.product_name}
                                  onChange={(e) => {
                                    const newData = [...extractedData];
                                    newData[idx].product_name = e.target.value;
                                    setExtractedData(newData);
                                  }}
                                  className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-full"
                                />
                              )}
                            </td>
                            <td className="p-3">
                              <input
                                type="text"
                                value={item.pack_label || ""}
                                onChange={(e) => {
                                  const newData = [...extractedData];
                                  newData[idx].pack_label = e.target.value;
                                  setExtractedData(newData);
                                }}
                                className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-20 font-mono text-yellow-400"
                              />
                            </td>
                            <td className="p-3">
                              <input
                                type="text"
                                value={item.batch_number}
                                onChange={(e) => {
                                  const newData = [...extractedData];
                                  newData[idx].batch_number = e.target.value;
                                  setExtractedData(newData);
                                }}
                                className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-24"
                              />
                            </td>
                            <td className="p-3">
                              <input
                                type="date"
                                value={item.expiry_date}
                                onChange={(e) => {
                                  const newData = [...extractedData];
                                  newData[idx].expiry_date = e.target.value;
                                  setExtractedData(newData);
                                }}
                                className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-32"
                              />
                            </td>
                            <td className="p-3">
                              <input
                                type="number"
                                value={item.quantity}
                                onChange={(e) => {
                                  const newData = [...extractedData];
                                  newData[idx].quantity = parseInt(e.target.value) || 0;
                                  setExtractedData(newData);
                                }}
                                className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-16 text-center"
                              />
                            </td>
                            <td className="p-3">
                              <div className="flex items-center">
                                <span className="text-gray-500 mr-1">₹</span>
                                <input
                                  type="number"
                                  step="0.01"
                                  value={item.buy_price || (item.mrp * 0.7).toFixed(2)}
                                  onChange={(e) => {
                                    const newData = [...extractedData];
                                    newData[idx].buy_price = parseFloat(e.target.value) || 0;
                                    setExtractedData(newData);
                                  }}
                                  className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-20"
                                />
                              </div>
                            </td>
                            <td className="p-3">
                              <div className="flex items-center">
                                <span className="text-gray-500 mr-1">₹</span>
                                <input
                                  type="number"
                                  step="0.01"
                                  value={item.mrp}
                                  onChange={(e) => {
                                    const newData = [...extractedData];
                                    newData[idx].mrp = parseFloat(e.target.value) || 0;
                                    setExtractedData(newData);
                                  }}
                                  className="bg-transparent border-b border-white/20 focus:border-blue-500 outline-none w-20"
                                />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <button
                      onClick={async () => {
                        try {
                          if (isMergeMode) {
                            // MERGE LOGIC
                            const response = await fetch('http://localhost:8000/api/invoices/merge', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({
                                items: extractedData,
                                summary: mergeSummary
                              })
                            });

                            if (!response.ok) throw new Error(`Merge failed: ${response.statusText}`);

                            const result = await response.json();
                            alert(`Merge Successful! Updated ${result.results.length} items.`);
                            setExtractedData([]);
                            setIsMergeMode(false);
                            setMergeSummary(null);
                            setActiveTab('inventory');
                          } else {
                            // NORMAL COMMIT LOGIC
                            const response = await fetch('http://localhost:8000/api/inventory/add', {
                              method: 'POST',
                              headers: {
                                'Content-Type': 'application/json',
                              },
                              body: JSON.stringify(extractedData),
                            })

                            if (!response.ok) {
                              throw new Error(`Commit failed: ${response.statusText}`)
                            }

                            const result = await response.json()
                            alert(`Success! ${result.results.length} items added to inventory.`)
                            setExtractedData([]) // Clear data after commit
                            setActiveTab('inventory') // Go to inventory tab
                          }
                        } catch (error) {
                          console.error("Error committing inventory:", error)
                          alert("Failed to commit to inventory. Please try again.")
                        }
                      }}
                      className={`mt-6 px-6 py-2 rounded-lg font-medium transition-colors cursor-pointer ${isMergeMode ? 'bg-yellow-600 hover:bg-yellow-500 text-white' : 'bg-green-600 hover:bg-green-500 text-white'}`}
                    >
                      {isMergeMode ? "Merge to Inventory" : "Commit to Inventory"}
                    </button>
                  </div>
                ) : (
                  <p className="text-gray-500">No data extracted or no file uploaded.</p>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
            <h1 className="text-3xl font-bold mb-4">Settings</h1>
            <p className="text-gray-400">Configure your application.</p>
          </div>
        )}

        {activeTab === 'profile' && (
          <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
            <h1 className="text-3xl font-bold mb-4">User Profile</h1>
            <p className="text-gray-400">Manage your account.</p>
          </div>
        )}

        {/* Product Form Modal */}
        <ProductForm
          isOpen={isProductFormOpen}
          initialData={productFormInitialData}
          onClose={() => {
            setIsProductFormOpen(false);
            setProductFormInitialData(null);
          }}
          onSubmit={(data) => {
            console.log("Product Data:", data);
            // If we were editing a new product from the grid, we might want to update the grid here
            // For now, just alert
            alert("Product Saved! The system would now run the CREATE Cypher queries.");
            setIsProductFormOpen(false);
            setProductFormInitialData(null);
          }}
        />

        {/* Scan Mode Modal */}
        {isScanModalOpen && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="w-96 rounded-xl bg-[#1a1a1a] p-6 border border-white/10 shadow-2xl">
              <h2 className="text-xl font-semibold mb-4">Scan Mode</h2>
              <div className="flex gap-4">
                <button
                  onClick={handleCameraClick}
                  className="flex-1 rounded-lg bg-blue-600 py-2 font-medium hover:bg-blue-500 cursor-pointer transition-colors"
                >
                  Camera
                </button>
                <button
                  onClick={handleUploadClick}
                  className="flex-1 rounded-lg bg-gray-700 py-2 font-medium hover:bg-gray-600 cursor-pointer transition-colors"
                >
                  Upload
                </button>
              </div>
              <button
                onClick={() => setIsScanModalOpen(false)}
                className="mt-6 w-full text-sm text-gray-400 hover:text-white cursor-pointer transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept="image/*,application/pdf"
          onChange={handleFileChange}
        />
      </main>
    </div>
  )
}

export default App
