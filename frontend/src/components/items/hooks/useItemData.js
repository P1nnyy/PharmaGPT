import { useState, useEffect } from 'react';
import {
    getReviewQueue,
    getAllProducts,
    getCategories
} from '../../../services/api';

export const useItemData = () => {
    const [reviewQueue, setReviewQueue] = useState([]);
    const [allItems, setAllItems] = useState([]);
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchData = async () => {
        try {
            setLoading(true);
            const [queue, items, cats] = await Promise.all([
                getReviewQueue(),
                getAllProducts(),
                getCategories()
            ]);
            setReviewQueue(queue);
            setAllItems(items);
            setCategories(cats);
        } catch (err) {
            console.error("Failed to fetch ItemMaster data", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    return {
        reviewQueue,
        allItems,
        categories,
        loading,
        setReviewQueue,
        setAllItems,
        refreshData: fetchData
    };
};
