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
      setIsScanModalOpen(false) // Close modal immediately or keep open? Let's close it and show loading in dashboard.
      setActiveTab('ingestion') // Switch to a view to show results

      const formData = new FormData()
      formData.append('file', file)

      try {
        const response = await fetch('http://localhost:8000/api/upload', {
          method: 'POST',
          body: formData,
        })

        if (!response.ok) {
          throw new Error(`Upload failed: ${response.statusText}`)
        }

        const result = await response.json()
        // Handle new response structure where data is items
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
                                  <span className="font-medium text-blue-400">{item.product_name}</span>
                                  <button
                                    onClick={() => {
                                      setProductFormInitialData({
                                        name: item.product_name,
                                        mrp: item.mrp,
                                        manufacturer: item.manufacturer || '',
                                        // Default values for new product
                                        conversion: 10,
                                        skuUnit: 'Strip',
                                        atomicUnit: 'Tablet',
                                        category: 'Tablet' // Default category
                                      });
                                      setIsProductFormOpen(true);
                                    }}
                                    className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded transition-colors"
                                  >
                                    Define
                                  </button>
                                </div>
                              ) : (
                                item.product_name
                              )}
                            </td>
                            <td className="p-3">{item.batch_number}</td>
                            <td className="p-3">{item.expiry_date}</td>
                            <td className="p-3">{item.quantity_packs}</td>
                            <td className="p-3">₹{item.rate || (item.mrp * 0.7).toFixed(2)}</td>
                            <td className="p-3">₹{item.mrp}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <button
                      onClick={async () => {
                        try {
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
                        } catch (error) {
                          console.error("Error committing inventory:", error)
                          alert("Failed to commit to inventory. Please try again.")
                        }
                      }}
                      className="mt-6 bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-lg font-medium transition-colors cursor-pointer"
                    >
                      Commit to Inventory
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
